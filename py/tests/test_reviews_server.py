"""Review ownership, anonymity, photo isolation and metadata regression tests."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import base64
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest
import zlib

import reviews
import server
from test_auth_server import Client, PASSWORD


def png(metadata=False):
    def chunk(kind, payload):
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack('!I', zlib.crc32(kind + payload))
    header = chunk(b'IHDR', struct.pack('!IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
    pixels = chunk(b'IDAT', zlib.compress(b'\0\xff\0\0\xff\0\0' * 2))
    return b'\x89PNG\r\n\x1a\n' + header + (chunk(b'tEXt', b'Author\0PRIVATE GPS PERSON') if metadata else b'') + pixels + chunk(b'IEND', b'')


def photo(data=None, mime='image/png', name='my-private-name.png'):
    return {'name': name, 'data': 'data:' + mime + ';base64,' + base64.b64encode(png() if data is None else data).decode('ascii')}


class ReviewServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.catalog = self.root / 'product-catalog.json'
        self.catalog.write_text('{"products":[]}', encoding='utf-8')
        self.database = self.root / '.velora/test.sqlite3'
        self.app = server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            for name, email in [('Maya Bennett', 'maya@example.test'), ('Lena Coleman', 'lena@example.test')]:
                connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,'customer',?)", (name, email, self.password_hash, server.now_iso()))
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.owner, self.other, self.public = Client(self.app), Client(self.app), Client(self.app)
        self.assertEqual(self.owner.login(email='maya@example.test')[0], 200)
        self.assertEqual(self.other.login(email='lena@example.test')[0], 200)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def payload(self, **changes):
        return {'rating': 5, 'title': 'A considered collection', 'body': 'I enjoyed exploring the collection and its different looks.', 'anonymous': False, **changes}

    def create(self, **changes):
        status, data, _ = self.owner.request('POST', '/api/reviews', self.payload(**changes))
        self.assertEqual(status, 201, data)
        return data['review']

    def upload(self, client=None, data=None):
        status, result, _ = (client or self.owner).request('POST', '/api/reviews/uploads', photo(data))
        self.assertEqual(status, 201, result)
        self.assertEqual(set(result), {'uploadToken'})
        self.assertRegex(result['uploadToken'], r'^[0-9a-f]{32}$')
        return result['uploadToken']

    def path(self, review):
        return '/api/reviews/' + review['id']

    def test_empty_public_summary_and_head(self):
        status, data, headers = self.public.request('GET', '/api/reviews')
        self.assertEqual(status, 200)
        self.assertEqual(data, {'reviews': [], 'summary': {'count': 0, 'average': 0, 'distribution': {str(i): 0 for i in range(1, 6)}}, 'nextCursor': None})
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.public.request('HEAD', '/api/reviews')[0:2], (200, b''))

    def test_name_is_server_derived_and_public_fields_are_explicit(self):
        review = self.create(body='A lovely concept. <script>not executable</script>')
        self.assertEqual(set(review), {'id', 'rating', 'title', 'body', 'authorName', 'anonymous', 'image', 'createdAt'})
        self.assertEqual(review['authorName'], 'Maya Bennett')
        self.assertFalse(review['anonymous'])
        self.assertIsNone(review['image'])
        data = self.public.request('GET', '/api/reviews')[1]
        self.assertEqual(data['reviews'], [review])
        self.assertEqual(data['summary']['count'], 1)
        self.assertEqual(data['summary']['average'], 5)
        self.assertEqual(data['summary']['distribution']['5'], 1)
        with self.app.connect() as connection:
            connection.execute("UPDATE users SET name='Maya Updated' WHERE email='maya@example.test'")
        self.assertEqual(self.public.request('GET', '/api/reviews')[1]['reviews'][0]['authorName'], 'Maya Updated')

    def test_anonymous_public_and_mine_do_not_leak_account_identity(self):
        review = self.create(anonymous=True)
        self.assertEqual(review['authorName'], 'Anonymous')
        public = self.public.request('GET', '/api/reviews')[1]
        encoded = json.dumps(public)
        self.assertNotIn('Maya', encoded)
        self.assertNotIn('maya@example', encoded)
        self.assertNotIn('user_id', encoded)
        self.assertNotIn('account_name', encoded)
        self.assertEqual(self.owner.request('GET', '/api/reviews/mine')[1]['review'], review)
        self.assertIsNone(self.other.request('GET', '/api/reviews/mine')[1]['review'])
        self.assertEqual(self.public.request('GET', '/api/reviews/mine')[0], 401)

    def test_authentication_csrf_and_origin_are_required(self):
        self.assertEqual(self.public.request('POST', '/api/reviews', self.payload())[0], 401)
        self.assertEqual(self.public.request('POST', '/api/reviews/uploads', photo())[0], 401)
        for endpoint, data in [('/api/reviews', self.payload()), ('/api/reviews/uploads', photo())]:
            self.assertEqual(self.owner.request('POST', endpoint, data, token=False)[0], 403)
            self.assertEqual(self.owner.request('POST', endpoint, data, origin=False)[0], 403)
        review = self.create()
        self.assertEqual(self.owner.request('PATCH', self.path(review), self.payload(), token=False)[0], 403)
        self.assertEqual(self.owner.request('DELETE', self.path(review), {}, origin=False)[0], 403)

    def test_rating_and_review_validation_rejects_spoofing(self):
        for value in [0, 6, True, 4.5, '5', None]:
            with self.subTest(rating=value):
                self.assertEqual(self.owner.request('POST', '/api/reviews', self.payload(rating=value))[0], 400)
        for changes in [{'body': 'too short'}, {'body': 'x' * 2001}, {'body': 25}, {'title': 'x' * 101}, {'title': None}, {'anonymous': 'true'}, {'anonymous': 1}, {'name': 'Spoofed Name'}, {'user_id': 2}, {'body': 'A review containing a bad\x01control character.'}, {'image': '../photo.png'}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.owner.request('POST', '/api/reviews', self.payload(**changes))[0], 400)

    def test_one_review_per_account_edit_and_delete(self):
        review = self.create()
        self.assertEqual(self.owner.request('POST', '/api/reviews', self.payload())[0], 409)
        status, result, _ = self.owner.request('PATCH', self.path(review), self.payload(rating=2, anonymous=True, title='', body='I have updated my perspective on the concept collection.'))
        self.assertEqual(status, 200)
        self.assertEqual(result['review']['createdAt'], review['createdAt'])
        self.assertEqual(result['review']['authorName'], 'Anonymous')
        self.assertEqual(result['review']['rating'], 2)
        self.assertEqual(self.public.request('GET', '/api/reviews')[1]['summary']['average'], 2)
        self.assertEqual(self.owner.request('DELETE', self.path(review), {})[1], {'deleted': True})
        self.assertIsNone(self.owner.request('GET', '/api/reviews/mine')[1]['review'])
        self.assertEqual(self.public.request('GET', '/api/reviews')[1]['summary']['count'], 0)
        self.create()

    def test_another_account_cannot_edit_delete_or_attach_private_upload(self):
        token = self.upload(self.other)
        self.assertEqual(self.owner.request('POST', '/api/reviews', self.payload(image=token))[0], 400)
        review = self.create()
        self.assertEqual(self.other.request('PATCH', self.path(review), self.payload())[0], 404)
        self.assertEqual(self.other.request('DELETE', self.path(review), {})[0], 404)
        self.assertEqual(self.public.request('DELETE', self.path(review), {})[0], 401)
        self.assertEqual(self.public.request('GET', '/api/reviews')[1]['reviews'][0], review)

    def test_uploaded_image_private_until_attached_and_metadata_removed(self):
        token = self.upload(data=png(metadata=True))
        image_path = '/api/reviews/images/' + token
        self.assertEqual(self.public.request('GET', image_path)[0], 404)
        review = self.create(image=token, anonymous=True)
        self.assertEqual(review['image'], image_path)
        status, image, headers = self.public.request('GET', image_path)
        self.assertEqual(status, 200)
        self.assertEqual(image, png())
        self.assertNotIn(b'PRIVATE GPS PERSON', image)
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.public.request('HEAD', image_path)[0:2], (200, b''))
        self.assertEqual(self.public.request('GET', '/.velora/review-images/' + token + '.png')[0], 404)
        self.assertNotIn('my-private-name', json.dumps(self.public.request('GET', '/api/reviews')[1]))

    def test_image_replacement_removal_and_deletion_cleanup(self):
        first = self.upload()
        review = self.create(image=first)
        second = self.upload()
        updated = self.owner.request('PATCH', self.path(review), self.payload(image=second))[1]['review']
        self.assertEqual(updated['image'], '/api/reviews/images/' + second)
        self.assertEqual(self.public.request('GET', '/api/reviews/images/' + first)[0], 404)
        # Omission retains the already published photo, even after 24 hours.
        with self.app.connect() as connection:
            connection.execute('UPDATE review_uploads SET created_at=0 WHERE id=?', (second,))
        updated = self.owner.request('PATCH', self.path(review), self.payload(title='Updated'))[1]['review']
        self.assertEqual(updated['image'], '/api/reviews/images/' + second)
        self.assertIsNone(self.owner.request('PATCH', self.path(review), self.payload(image=None))[1]['review']['image'])
        self.assertEqual(self.public.request('GET', '/api/reviews/images/' + second)[0], 404)
        third = self.upload()
        self.assertEqual(self.owner.request('PATCH', self.path(review), self.payload(image=third))[0], 200)
        self.assertEqual(self.owner.request('DELETE', self.path(review), {})[0], 200)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM review_uploads').fetchone()[0], 0)

    def test_account_deletion_cascades_review_and_pending_and_public_images(self):
        token = self.upload()
        self.create(image=token)
        self.upload()  # A separate, unpublished replacement draft.
        self.assertEqual(self.owner.request('DELETE', '/api/account', {'password': PASSWORD})[0], 200)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM customer_reviews').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM review_uploads').fetchone()[0], 0)
        self.assertEqual(self.public.request('GET', '/api/reviews/images/' + token)[0], 404)
        self.assertEqual(self.public.request('GET', '/api/reviews')[1]['summary']['count'], 0)

    def test_pending_upload_replacement_and_expiration(self):
        first = self.upload()
        second = self.upload()
        with self.app.connect() as connection:
            self.assertIsNone(connection.execute('SELECT 1 FROM review_uploads WHERE id=?', (first,)).fetchone())
            connection.execute('UPDATE review_uploads SET created_at=0 WHERE id=?', (second,))
        self.assertEqual(self.owner.request('POST', '/api/reviews', self.payload(image=second))[0], 400)
        self.assertEqual(self.public.request('GET', '/api/reviews/images/' + second)[0], 404)
        self.upload()
        with self.app.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM review_uploads').fetchone()[0], 1)

    def test_photo_validation_rejects_wrong_format_broken_chunks_and_large_files(self):
        for data in [photo(b'<svg xmlns="http://www.w3.org/2000/svg"/>', 'image/png'), photo(png(), 'image/jpeg'), {'name': 'x', 'data': 'data:image/svg+xml;base64,PHN2Zz4='}, photo(png()[:-5]), photo(png()[:35] + b'bad!' + png()[39:]), {'name': '', 'data': photo()['data']}]:
            with self.subTest(data=str(data)[:80]):
                self.assertEqual(self.owner.request('POST', '/api/reviews/uploads', data)[0], 400)
        self.assertEqual(self.owner.request('POST', '/api/reviews/uploads', photo(b'x' * (reviews.MAX_IMAGE_BYTES + 1)))[0], 413)

    def test_pagination_is_stable_across_new_posts_and_summary_covers_all(self):
        with self.app.connect() as connection:
            for index in range(7):
                user = connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,'customer',?)", (f'Reader {index}', f'reader{index}@example.test', self.password_hash, server.now_iso())).lastrowid
                connection.execute('INSERT INTO customer_reviews (id,user_id,rating,title,body,anonymous,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', (f'{index + 1:032x}', user, index % 5 + 1, '', f'Review number {index} from an account.', 0, server.now_iso(), server.now_iso()))
        first = self.public.request('GET', '/api/reviews?limit=3')[1]
        self.assertEqual(len(first['reviews']), 3)
        self.assertEqual(first['summary']['count'], 7)
        self.assertIsNotNone(first['nextCursor'])
        new = self.create()
        second = self.public.request('GET', '/api/reviews?limit=3&cursor=' + first['nextCursor'])[1]
        third = self.public.request('GET', '/api/reviews?limit=3&cursor=' + second['nextCursor'])[1]
        ids = [item['id'] for page in (first, second, third) for item in page['reviews']]
        self.assertEqual(len(ids), 7)
        self.assertEqual(len(set(ids)), 7)
        self.assertNotIn(new['id'], ids)
        self.assertIsNone(third['nextCursor'])
        self.assertEqual(third['summary']['count'], 8)
        self.assertEqual(sum(third['summary']['distribution'].values()), 8)

    def test_bad_pagination_unknown_routes_and_methods(self):
        for query in ['limit=0', 'limit=25', 'limit=-1', 'limit=all', 'limit=2&limit=3', 'cursor=', 'cursor=bad_cursor', 'sort=name']:
            with self.subTest(query=query):
                self.assertEqual(self.public.request('GET', '/api/reviews?' + query)[0], 400)
        self.assertEqual(self.owner.request('PUT', '/api/reviews', {})[0], 405)
        self.assertEqual(self.public.request('GET', '/api/reviews/uploads')[0], 405)
        self.assertEqual(self.public.request('GET', '/api/reviews/unknown')[0], 404)

    def test_jpeg_app_and_comment_metadata_removed_including_between_scans(self):
        # Structural fixture tests segment scanning without requiring Pillow.
        segment = lambda marker, data: b'\xff' + bytes([marker]) + struct.pack('!H', len(data) + 2) + data
        sof = segment(0xC0, b'\x08\x00\x02\x00\x02\x01\x01\x11\x00')
        sos = segment(0xDA, b'\x01\x01\x00\x00\x3f\x00')
        clean = b'\xff\xd8' + sof + sos + b'\x01\xff\x00\x02' + b'\xff\xd9'
        dirty = b'\xff\xd8' + segment(0xE1, b'Exif\0GPS private author') + segment(0xED, b'IPTC private name') + sof + sos + b'\x01\xff\x00\x02' + segment(0xFE, b'private comment') + b'\xff\xd9'
        self.assertEqual(reviews.clean_image(photo(dirty, 'image/jpeg'), server.image_extension)[0], clean)
        self.assertEqual(server.image_extension(clean), 'jpg')

    def test_webp_metadata_removed_and_animation_rejected(self):
        chunk = lambda kind, data: kind + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')
        wrap = lambda content: b'RIFF' + struct.pack('<I', len(content) + 4) + b'WEBP' + content
        vp8x = chunk(b'VP8X', b'\x2c\0\0\0\x01\0\0\x01\0\0')
        vp8l = chunk(b'VP8L', b'\x2f\x01\x40\0\0')
        dirty = wrap(vp8x + chunk(b'EXIF', b'PRIVATE GPS NAME') + vp8l + chunk(b'XMP ', b'PRIVATE AUTHOR'))
        cleaned = reviews.clean_image(photo(dirty, 'image/webp'), server.image_extension)[0]
        self.assertNotIn(b'PRIVATE', cleaned)
        self.assertEqual(cleaned[20], 0)
        self.assertEqual(server.image_extension(cleaned), 'webp')
        animated = wrap(chunk(b'VP8X', b'\x02\0\0\0\x01\0\0\x01\0\0') + chunk(b'ANIM', b'\0' * 6) + vp8l)
        with self.assertRaises(reviews.ReviewError):
            reviews.clean_image(photo(animated, 'image/webp'), server.image_extension)

    def test_review_rate_limit(self):
        with self.app.rate_lock:
            self.app.rate_events[('review-write', 1)] = [time.time()] * 30
        self.assertEqual(self.owner.request('POST', '/api/reviews', self.payload())[0], 429)


if __name__ == '__main__':
    unittest.main()
