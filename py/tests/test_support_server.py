"""Support privacy, guest isolation, authorization and live polling contracts."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import commerce
import server
import support
from test_auth_server import Client, PASSWORD


class SupportServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        catalog = self.root / 'catalog.json'
        catalog.write_text('{"products":[]}', encoding='utf-8')
        self.app = server.make_server(port=0, root=self.root, database=self.root / '.velora/test.sqlite3', catalog=catalog)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            for email, role, name in [('support', 'admin', 'Support Owner'), ('manager', 'admin', 'Support Manager'), ('warehouse', 'admin', 'Warehouse Staff'), ('maya', 'customer', 'Maya Customer'), ('lena', 'customer', 'Lena Customer')]:
                connection.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                    (name, email + '@example.test', self.password_hash, role, server.now_iso()))
            operations = json.loads(connection.execute('SELECT data FROM commerce_state WHERE id=1').fetchone()[0])
            operations['staff'] = {'2': 'manager', '3': 'warehouse'}
            connection.execute('UPDATE commerce_state SET data=? WHERE id=1', (json.dumps(operations),))
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.owner, self.customer, self.public = Client(self.app), Client(self.app), Client(self.app)
        self.assertEqual(self.owner.login(email='support@example.test')[0], 200)
        self.assertEqual(self.customer.login(email='maya@example.test')[0], 200)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def guest(self):
        guest = Client(self.app)
        status, data, headers = guest.request('GET', '/api/support/session')
        self.assertEqual(status, 200, data)
        self.assertTrue(data['customer']['guest'])
        return guest, data, headers

    def send(self, client=None, **changes):
        client = client or self.customer
        payload = {'body': 'Hello, I need help choosing my size.', 'clientId': secrets.token_hex(16), **changes}
        status, data, _ = client.request('POST', '/api/support/messages', payload)
        self.assertEqual(status, 201, data)
        return data

    def reply(self, thread_id, **changes):
        status, data, _ = self.owner.request('POST', '/api/admin/support/' + thread_id + '/messages',
            {'body': 'Hello Maya, how can I help?', 'clientId': secrets.token_hex(16), **changes})
        self.assertEqual(status, 201, data)
        return data

    def test_guest_cookie_only_when_support_session_is_opened(self):
        health = self.public.request('GET', '/api/health')
        self.assertNotIn('Set-Cookie', health[2])
        self.assertEqual(self.public.request('GET', '/api/support/conversation')[0], 401)
        guest, data, headers = self.guest()
        self.assertEqual(data['customer'], {'name': 'Guest', 'guest': True})
        self.assertIsNone(data['conversation'])
        self.assertEqual(data['availability'], {'online': False})
        cookie = headers['Set-Cookie']
        for part in ['velora_support=', 'HttpOnly', 'SameSite=Strict', 'Path=/api/support', 'Max-Age=604800']:
            self.assertIn(part, cookie)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Set-Cookie', guest.request('GET', '/api/support/session')[2])

    def test_guest_messages_are_private_and_use_optional_display_name(self):
        guest, _, _ = self.guest()
        first = self.send(guest, name='A guest customer', body='Can you help me with a size chart?')
        self.assertEqual(first['conversation']['customerName'], 'A guest customer')
        self.assertEqual(first['message']['authorName'], 'A guest customer')
        other, _, _ = self.guest()
        self.assertIsNone(other.request('GET', '/api/support/conversation')[1]['conversation'])
        self.assertEqual(other.request('GET', '/api/support/conversation?conversation=' + first['conversation']['id'])[0], 400)
        self.assertEqual(self.public.request('GET', '/api/admin/support/' + first['conversation']['id'])[0], 401)
        self.assertEqual(set(first['message']), {'id', 'body', 'sender', 'authorName', 'createdAt'})
        self.assertEqual(set(first['conversation']), {'id', 'customerName', 'status', 'updatedAt', 'lastMessage', 'unreadCount'})

    def test_signed_in_identity_comes_from_account_not_guest_or_payload(self):
        session = self.customer.request('GET', '/api/support/session')[1]
        self.assertEqual(session['customer'], {'name': 'Maya Customer', 'guest': False})
        self.assertNotIn('Set-Cookie', self.customer.request('GET', '/api/support/session')[2])
        sent = self.send()
        self.assertEqual(sent['message']['authorName'], 'Maya Customer')
        self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': 'This must not spoof an author.', 'clientId': secrets.token_hex(16), 'name': 'Someone else'})[0], 400)
        self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': 'This must not choose a thread.', 'clientId': secrets.token_hex(16), 'conversationId': 'f' * 32})[0], 400)
        with self.app.connect() as connection:
            connection.execute("UPDATE users SET name='Maya Updated' WHERE id=4")
        self.assertEqual(self.customer.request('GET', '/api/support/conversation')[1]['messages'][0]['authorName'], 'Maya Updated')

    def test_guest_and_account_conversations_are_never_merged(self):
        guest, _, _ = self.guest()
        old = self.send(guest)
        guest_cookie = guest.cookie
        self.assertEqual(guest.login(email='maya@example.test')[0], 200)
        guest.cookie += '; ' + guest_cookie
        self.assertIsNone(guest.request('GET', '/api/support/session')[1]['conversation'])
        account = self.send(guest)
        self.assertNotEqual(account['conversation']['id'], old['conversation']['id'])
        self.assertEqual(guest.request('GET', '/api/support/conversation')[1]['messages'][0]['authorName'], 'Maya Customer')

    def test_guest_and_user_csrf_origin_checks(self):
        guest, _, _ = self.guest()
        for client in [guest, self.customer]:
            payload = {'body': 'A customer support request.', 'clientId': secrets.token_hex(16)}
            self.assertEqual(client.request('POST', '/api/support/messages', payload, token=False)[0], 403)
            self.assertEqual(client.request('POST', '/api/support/messages', payload, origin=False)[0], 403)
        self.assertEqual(guest.request('DELETE', '/api/support/conversation', {}, token=False)[0], 403)

    def test_optional_history_token_binds_poll_to_opened_identity(self):
        first = self.send(body='This is Maya private conversation.')
        other = Client(self.app)
        self.assertEqual(other.login(email='lena@example.test')[0], 200)
        second = self.send(other, body='This is Lena private conversation.')
        guest, _, _ = self.guest()
        guest_thread = self.send(guest, name='Private Guest')
        for client, wrong_token in [(other, self.customer.csrf), (other, guest.csrf), (guest, self.customer.csrf)]:
            with self.subTest(identity=client.cookie[:24], wrong_token_kind='another identity'):
                self.assertEqual(client.request('GET', '/api/support/conversation', extra_headers={'X-CSRF-Token': wrong_token})[0], 403)
                self.assertEqual(client.request('GET', '/api/support/conversation?before=999999', extra_headers={'X-CSRF-Token': wrong_token})[0], 403)
        for client, thread in [(self.customer, first), (other, second), (guest, guest_thread)]:
            bound = client.request('GET', '/api/support/conversation', extra_headers={'X-CSRF-Token': client.csrf})
            self.assertEqual(bound[0], 200, bound[1])
            self.assertEqual(bound[1]['conversation']['id'], thread['conversation']['id'])
            headerless = client.request('GET', '/api/support/conversation')
            self.assertEqual(headerless[0], 200)
            self.assertEqual(headerless[1]['conversation']['id'], thread['conversation']['id'])
        self.assertEqual(other.request('GET', '/api/support/conversation', extra_headers={'X-CSRF-Token': ''})[0], 403)

    def test_staff_permissions_and_transaction_role_recheck(self):
        thread_id = self.send()['conversation']['id']
        self.assertEqual(self.customer.request('GET', '/api/admin/support')[0], 403)
        warehouse, manager = Client(self.app), Client(self.app)
        self.assertEqual(warehouse.login(email='warehouse@example.test')[0], 200)
        # Manager uses a distinct email because both names begin with Support.
        with self.app.connect() as connection:
            connection.execute("UPDATE users SET email='manager@example.test' WHERE id=2")
        self.assertEqual(manager.login(email='manager@example.test')[0], 200)
        self.assertEqual(warehouse.request('GET', '/api/admin/support')[0], 403)
        self.assertEqual(warehouse.request('POST', '/api/admin/support/presence', {'available': True})[0], 403)
        self.assertEqual(manager.request('GET', '/api/admin/support')[0], 200)
        self.assertEqual(manager.request('POST', '/api/admin/support/' + thread_id + '/messages', {'body': 'A manager response.', 'clientId': secrets.token_hex(16)})[0], 201)
        with patch.object(commerce, 'role', side_effect=['owner', 'warehouse']):
            self.assertEqual(self.owner.request('POST', '/api/admin/support/' + thread_id + '/messages', {'body': 'Must not be sent after a role change.', 'clientId': secrets.token_hex(16)})[0], 403)

    def test_live_poll_reply_read_counts_and_reopen(self):
        first = self.send()
        thread_id, first_id = first['conversation']['id'], first['message']['id']
        inbox = self.owner.request('GET', '/api/admin/support')[1]
        self.assertEqual(inbox['unreadCount'], 1)
        self.assertEqual(inbox['conversations'][0]['unreadCount'], 1)
        self.assertEqual(self.owner.request('POST', '/api/admin/support/' + thread_id + '/read', {'through': first_id})[1]['conversation']['unreadCount'], 0)
        response = self.reply(thread_id)
        polled = self.customer.request('GET', '/api/support/conversation?after=' + str(first_id))[1]
        self.assertEqual([m['id'] for m in polled['messages']], [response['message']['id']])
        self.assertEqual(polled['conversation']['unreadCount'], 1)
        self.assertEqual(response['message']['authorName'], 'Support Owner')
        self.assertEqual(self.customer.request('POST', '/api/support/read', {'through': response['message']['id']})[1]['conversation']['unreadCount'], 0)
        self.assertEqual(self.owner.request('PATCH', '/api/admin/support/' + thread_id, {'status': 'closed'})[1]['conversation']['status'], 'closed')
        self.assertEqual(self.send()['conversation']['status'], 'open')

    def test_retry_idempotency_for_customer_and_staff(self):
        client_id = secrets.token_hex(16)
        first, retry = self.send(clientId=client_id), self.send(clientId=client_id)
        self.assertEqual(first['message']['id'], retry['message']['id'])
        self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': 'A different message.', 'clientId': client_id})[0], 409)
        thread_id = first['conversation']['id']
        first_reply, retried_reply = self.reply(thread_id, clientId=client_id), self.reply(thread_id, clientId=client_id)
        self.assertEqual(first_reply['message']['id'], retried_reply['message']['id'])
        self.assertEqual(len(self.customer.request('GET', '/api/support/conversation')[1]['messages']), 2)

    def test_read_cursor_cannot_mark_unknown_or_other_conversation_messages(self):
        guest, _, _ = self.guest()
        foreign = self.send(guest)
        own = self.send()
        for value in [True, 0, -1, '1', 10 ** 25]:
            self.assertEqual(self.customer.request('POST', '/api/support/read', {'through': value})[0], 400)
        self.assertEqual(self.customer.request('POST', '/api/support/read', {'through': foreign['message']['id']})[0], 404)
        self.assertEqual(self.owner.request('POST', '/api/admin/support/' + own['conversation']['id'] + '/read', {'through': foreign['message']['id']})[0], 404)
        self.assertEqual(self.customer.request('POST', '/api/support/read', {'through': own['message']['id']})[0], 200)

    def test_presence_is_real_expires_and_revoked_sessions_are_offline(self):
        self.assertFalse(self.customer.request('GET', '/api/support/session')[1]['availability']['online'])
        present = self.owner.request('POST', '/api/admin/support/presence', {'available': True})
        self.assertEqual(present[1], {'availability': {'online': True}, 'expiresIn': 45})
        self.assertTrue(self.customer.request('GET', '/api/support/session')[1]['availability']['online'])
        with patch.object(support.time, 'time', return_value=time.time() + 46):
            self.assertFalse(self.customer.request('GET', '/api/support/session')[1]['availability']['online'])
        self.owner.request('POST', '/api/admin/support/presence', {'available': True})
        self.owner.request('POST', '/api/auth/logout', {})
        self.assertFalse(self.customer.request('GET', '/api/support/session')[1]['availability']['online'])

    def test_presence_off_and_warehouse_permission_change(self):
        self.owner.request('POST', '/api/admin/support/presence', {'available': True})
        self.assertFalse(self.owner.request('POST', '/api/admin/support/presence', {'available': False})[1]['availability']['online'])
        self.owner.request('POST', '/api/admin/support/presence', {'available': True})
        with self.app.connect() as connection:
            data = json.loads(connection.execute('SELECT data FROM commerce_state WHERE id=1').fetchone()[0])
            data['staff']['1'] = 'warehouse'
            connection.execute('UPDATE commerce_state SET data=? WHERE id=1', (json.dumps(data),))
        self.assertFalse(self.customer.request('GET', '/api/support/session')[1]['availability']['online'])

    def test_message_history_latest_earlier_and_after_pagination(self):
        messages = [self.send(body=f'Message {number}')['message'] for number in range(5)]
        latest = self.customer.request('GET', '/api/support/conversation?limit=2')[1]
        self.assertEqual([m['id'] for m in latest['messages']], [m['id'] for m in messages[-2:]])
        self.assertTrue(latest['hasEarlier'])
        self.assertFalse(latest['hasMore'])
        earlier = self.customer.request('GET', '/api/support/conversation?limit=2&before=' + str(latest['nextBefore']))[1]
        self.assertEqual([m['id'] for m in earlier['messages']], [m['id'] for m in messages[1:3]])
        following = self.customer.request('GET', '/api/support/conversation?limit=2&after=' + str(messages[0]['id']))[1]
        self.assertTrue(following['hasMore'])
        self.assertEqual(following['nextAfter'], messages[2]['id'])
        self.assertEqual(self.customer.request('GET', '/api/support/conversation?after=' + str(messages[-1]['id']))[1]['messages'], [])

    def test_staff_inbox_filters_cursor_and_global_unread(self):
        customer_thread = self.send()['conversation']['id']
        for _ in range(3):
            guest, _, _ = self.guest()
            self.send(guest)
        first = self.owner.request('GET', '/api/admin/support?status=all&limit=2')[1]
        second = self.owner.request('GET', '/api/admin/support?status=all&limit=2&before=' + first['nextCursor'])[1]
        self.assertEqual(len({r['id'] for r in first['conversations'] + second['conversations']}), 4)
        self.assertIsNone(second['nextCursor'])
        self.assertEqual(first['unreadCount'], 4)
        self.owner.request('PATCH', '/api/admin/support/' + customer_thread, {'status': 'closed'})
        closed = self.owner.request('GET', '/api/admin/support?status=closed')[1]
        self.assertEqual([r['id'] for r in closed['conversations']], [customer_thread])

    def test_delete_own_conversation_cascades_messages_and_allows_new_thread(self):
        first = self.send()
        self.reply(first['conversation']['id'])
        self.assertEqual(self.customer.request('DELETE', '/api/support/conversation', {})[1], {'deleted': True})
        self.assertIsNone(self.customer.request('GET', '/api/support/conversation')[1]['conversation'])
        self.assertEqual(self.owner.request('GET', '/api/admin/support/' + first['conversation']['id'])[0], 404)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM support_messages').fetchone()[0], 0)
        self.assertNotEqual(self.send()['conversation']['id'], first['conversation']['id'])

    def test_guest_delete_also_clears_saved_display_name(self):
        guest, _, _ = self.guest()
        self.send(guest, name='Name to remove')
        self.assertEqual(guest.request('GET', '/api/support/session')[1]['customer']['name'], 'Name to remove')
        self.assertEqual(guest.request('DELETE', '/api/support/conversation', {})[0], 200)
        session = guest.request('GET', '/api/support/session')[1]
        self.assertEqual(session['customer'], {'name': 'Guest', 'guest': True})
        self.assertIsNone(session['conversation'])

    def test_account_deletion_cascades_customer_thread_and_messages(self):
        thread_id = self.send()['conversation']['id']
        self.reply(thread_id)
        self.assertEqual(self.customer.request('DELETE', '/api/account', {'password': PASSWORD})[0], 200)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM support_conversations').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM support_messages').fetchone()[0], 0)

    def test_guest_expiry_retention_and_secure_cookie(self):
        guest, data, _ = self.guest()
        thread_id = self.send(guest)['conversation']['id']
        with self.app.connect() as connection:
            connection.execute('UPDATE support_guests SET expires_at=?', (int(time.time()) - 1,))
        self.assertEqual(guest.request('GET', '/api/support/conversation')[0], 401)
        new_session = guest.request('GET', '/api/support/session')[1]
        self.assertNotEqual(new_session['csrfToken'], data['csrfToken'])
        self.assertIsNone(new_session['conversation'])
        with self.app.connect() as connection:
            connection.execute('UPDATE support_guests SET last_seen=? WHERE id=(SELECT guest_id FROM support_conversations WHERE id=?)', (int(time.time()) - support.GUEST_RETENTION_SECONDS - 1, thread_id))
            support.cleanup(connection)
            self.assertIsNone(connection.execute('SELECT id FROM support_conversations WHERE id=?', (thread_id,)).fetchone())
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM support_messages').fetchone()[0], 0)
        self.assertIn('; Secure', support.guest_cookie('test', True))

    def test_validation_methods_and_payloads(self):
        for body in ['', '  ', 'a' * 2001, '\x00hidden', 2, None]:
            self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': body, 'clientId': secrets.token_hex(16)})[0], 400)
        for client_id in [None, '', 'short', 'x' * 33]:
            self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': 'Hello', 'clientId': client_id})[0], 400)
        self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': '<script>alert(1)</script>', 'clientId': '12345678-1234-1234-1234-123456789abc'})[1]['message']['body'], '<script>alert(1)</script>')
        for query in ['limit=0', 'limit=101', 'after=-1', 'after=1&before=2', 'after=1&after=2', 'unknown=1']:
            self.assertEqual(self.customer.request('GET', '/api/support/conversation?' + query)[0], 400)
        self.assertEqual(self.owner.request('GET', '/api/admin/support?before=bad')[0], 400)
        self.assertEqual(self.owner.request('GET', '/api/admin/support?status=invalid')[0], 400)
        self.assertEqual(self.customer.request('PUT', '/api/support/messages', {})[0], 405)
        self.assertEqual(self.customer.request('GET', '/api/support/unknown')[0], 404)

    def test_rate_limits_and_expired_sessions_do_not_write(self):
        with self.app.rate_lock:
            self.app.rate_events[('support-message', 'user:4')] = [time.time()] * 60
        self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': 'Please help.', 'clientId': secrets.token_hex(16)})[0], 429)
        self.customer.request('POST', '/api/auth/logout', {})
        self.assertEqual(self.customer.request('POST', '/api/support/messages', {'body': 'Please help.', 'clientId': secrets.token_hex(16)})[0], 401)


if __name__ == '__main__':
    unittest.main()
