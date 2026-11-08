"""Seasonal code persistence, server-priced previews and administrator boundaries."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest import mock

import test_catalog_server as catalog_tests
from test_auth_server import Client, PASSWORD
import discounts
import server


class DiscountServerTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__["setUpClass"]
    setUp = catalog_tests.CatalogServerTests.setUp
    tearDown = catalog_tests.CatalogServerTests.tearDown

    def create(self, client=None, **changes):
        payload = {"code": "BLACKFRIDAY20", "name": "Black Friday edit", "theme": "black-friday", "type": "percent",
                   "amount": 20, "minSubtotal": 0, "startsAt": None, "endsAt": None, "active": True, **changes}
        response = (client or self.admin).request("POST", "/api/admin/discounts", payload)
        self.assertEqual(response[0], 201, response[1])
        return response[1]["discount"]

    def quote(self, code="BLACKFRIDAY20", items=None, **changes):
        return self.public.request("POST", "/api/discounts/validate", {
            "code": code, "items": items if items is not None else [{"productId": "123456789abcdef0", "quantity": 1}], **changes,
        })

    def test_create_list_edit_and_delete_are_persistent_and_audited(self):
        code = self.create(code="  halloween-15  ", name="Halloween evening edit", theme="halloween", amount=15,
                           startsAt="2020-01-01T01:00:00+01:00", endsAt="2099-01-01T00:00:00Z")
        self.assertEqual(code["code"], "HALLOWEEN-15")
        self.assertEqual(code["startsAt"], "2020-01-01T00:00:00Z")
        status, data, headers = self.admin.request("GET", "/api/admin/discounts")
        self.assertEqual(status, 200)
        self.assertEqual(data["discounts"], [code])
        self.assertEqual(data["currency"], "EUR")
        self.assertIn("halloween", {item["id"] for item in data["themes"]})
        self.assertIn("no-store", headers["Cache-Control"])
        status, edited, _ = self.admin.request("PATCH", f"/api/admin/discounts/{code['id']}", {"amount": 25, "active": False})
        self.assertEqual(status, 200, edited)
        self.assertEqual(edited["discount"]["amount"], 25)
        self.assertFalse(edited["discount"]["active"])
        with self.app.connect() as connection:
            stored = connection.execute("SELECT * FROM discount_codes WHERE id=?", (code["id"],)).fetchone()
            self.assertEqual(stored["amount_units"], 2500)
            self.assertEqual(stored["active"], 0)
        self.assertEqual(self.admin.request("DELETE", f"/api/admin/discounts/{code['id']}")[0], 200)
        self.assertEqual(self.admin.request("GET", "/api/admin/discounts")[1]["discounts"], [])
        self.assertEqual(self.quote("HALLOWEEN-15")[0], 400)
        with self.app.connect() as connection:
            events = {row[0] for row in connection.execute("SELECT event_type FROM security_events")}
        self.assertTrue({"discount_created", "discount_updated", "discount_deleted"}.issubset(events))

    def test_preview_uses_current_catalog_prices_accurate_rounding_and_no_redemption(self):
        self.create(amount=12.5)
        with self.app.connect() as connection:
            connection.execute("UPDATE products SET price=100.05 WHERE id='123456789abcdef0'")
            before = connection.execute("SELECT data FROM commerce_state").fetchone()[0]
            discount_before = tuple(connection.execute("SELECT * FROM discount_codes").fetchone())
        status, quote, _ = self.quote("blackfriday20", items=[
            {"productId": "123456789abcdef0", "quantity": 1}, {"productId": "123456789abcdef0", "quantity": 1},
        ])
        self.assertEqual(status, 200, quote)
        self.assertEqual((quote["subtotalCents"], quote["discountCents"], quote["totalCents"]), (20010, 2501, 17509))
        self.assertEqual(quote["scope"], "bag-preview")
        self.assertEqual(quote["currency"], "EUR")
        self.assertNotIn("created_by", quote)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT data FROM commerce_state").fetchone()[0], before)
            self.assertEqual(tuple(connection.execute("SELECT * FROM discount_codes").fetchone()), discount_before)
            connection.execute("UPDATE products SET price=1.01 WHERE id='123456789abcdef0'")
        self.create(code="HALF", amount=50)
        self.assertEqual(self.quote("HALF")[1]["discountCents"], 51)
        self.create(code="GIFT100", type="fixed", amount=100)
        capped = self.quote("GIFT100")[1]
        self.assertEqual((capped["subtotalCents"], capped["discountCents"], capped["totalCents"]), (101, 101, 0))

    def test_dates_minimum_spend_and_deactivation_take_effect_on_next_quote(self):
        start = datetime(2030, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        code = self.create(startsAt=start.isoformat(), endsAt=end.isoformat(), minSubtotal=240)
        with mock.patch.object(discounts, "now", return_value=start - timedelta(seconds=1)):
            self.assertEqual(self.quote()[0], 400)
        with mock.patch.object(discounts, "now", return_value=start):
            self.assertEqual(self.quote()[0], 200)
        with mock.patch.object(discounts, "now", return_value=end):
            self.assertEqual(self.quote()[0], 400)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/discounts/{code['id']}", {"startsAt": None, "endsAt": None, "minSubtotal": 240.01})[0], 200)
        self.assertEqual(self.quote()[0], 400)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/discounts/{code['id']}", {"minSubtotal": 0})[0], 200)
        self.assertEqual(self.quote()[0], 200)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/discounts/{code['id']}", {"active": False})[0], 200)
        self.assertEqual(self.quote()[0], 400)

    def test_code_uniqueness_generation_and_field_validation(self):
        self.create()
        self.assertEqual(self.admin.request("POST", "/api/admin/discounts", {
            "code": "blackfriday20", "name": "Duplicate", "theme": "custom", "type": "fixed", "amount": 10,
            "minSubtotal": 0, "startsAt": None, "endsAt": None, "active": False,
        })[0], 409)
        generated = self.create(code="", theme="halloween")
        self.assertTrue(generated["code"].startswith("HALLOWEEN-"))
        base = {"code": "NEWCODE", "name": "Test campaign", "theme": "custom", "type": "percent", "amount": 10,
                "minSubtotal": 0, "startsAt": None, "endsAt": None, "active": False}
        for changes in ({"code": "x"}, {"code": "bad code"}, {"name": "\nUnsafe"}, {"theme": "unknown"}, {"type": "free"},
                        {"amount": True}, {"amount": 0}, {"amount": 100.01}, {"amount": 3.333}, {"minSubtotal": -1},
                        {"active": 1}, {"startsAt": "2030-01-01T00:00:00"}, {"endsAt": "invalid"},
                        {"startsAt": "2030-01-02T00:00:00Z", "endsAt": "2030-01-01T00:00:00Z"}, {"extra": True}):
            with self.subTest(changes=changes):
                self.assertEqual(self.admin.request("POST", "/api/admin/discounts", {**base, **changes})[0], 400)
        self.assertEqual(self.admin.request("POST", "/api/admin/discounts", {"code": "INCOMPLETE"})[0], 400)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/discounts/{generated['id']}", {"code": "BLACKFRIDAY20"})[0], 409)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/discounts/{generated['id']}", {"amount": -1})[0], 400)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/discounts/{generated['id']}", {"createdBy": 42})[0], 400)

    def test_quote_rejects_tampered_totals_invalid_quantities_and_unavailable_products(self):
        self.create()
        self.assertEqual(self.quote(subtotal=1)[0], 400)
        for items in ([], [{"productId": "missing", "quantity": 1}], [{"productId": "123456789abcdef0", "quantity": 0}],
                      [{"productId": "123456789abcdef0", "quantity": True}], [{"productId": "123456789abcdef0", "quantity": 1.5}],
                      [{"productId": "123456789abcdef0", "quantity": 101}], [{"productId": "123456789abcdef0", "quantity": 1, "price": .01}],
                      [{"productId": "123456789abcdef0", "quantity": 60}, {"productId": "123456789abcdef0", "quantity": 41}]):
            with self.subTest(items=items):
                self.assertEqual(self.quote(items=items)[0], 400)
        with self.app.connect() as connection:
            connection.execute("UPDATE products SET stock=0 WHERE id='123456789abcdef0'")
        self.assertEqual(self.quote()[0], 400)
        with self.app.connect() as connection:
            connection.execute("UPDATE products SET stock=1,published=0 WHERE id='123456789abcdef0'")
        self.assertEqual(self.quote()[0], 400)
        with self.app.connect() as connection:
            connection.execute("UPDATE products SET published=1,deleted_at=? WHERE id='123456789abcdef0'", (server.now_iso(),))
        self.assertEqual(self.quote()[0], 400)

    def staff_account(self, role):
        with self.app.connect() as connection:
            key = connection.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", ("Staff", f"{role}@velora.com", self.password_hash, server.now_iso())).lastrowid
            state = json.loads(connection.execute("SELECT data FROM commerce_state").fetchone()[0])
            state["staff"][str(key)] = role
            connection.execute("UPDATE commerce_state SET data=?", (json.dumps(state),))
        client = Client(self.app)
        self.assertEqual(client.login(email=f"{role}@velora.com")[0], 200)
        return client, key

    def test_owner_and_manager_can_manage_but_customers_and_warehouse_cannot(self):
        customer = Client(self.app)
        self.assertEqual(customer.register()[0], 201)
        manager, _ = self.staff_account("manager")
        warehouse, _ = self.staff_account("warehouse")
        for client, expected in ((self.public, 401), (customer, 403), (warehouse, 403)):
            self.assertEqual(client.request("GET", "/api/admin/discounts")[0], expected)
            self.assertEqual(client.request("POST", "/api/admin/discounts", {})[0], expected)
        managed = self.create(client=manager)
        self.assertEqual(manager.request("GET", "/api/admin/discounts")[0], 200)
        self.assertEqual(manager.request("PATCH", f"/api/admin/discounts/{managed['id']}", {"active": False})[0], 200)
        self.assertEqual(warehouse.request("DELETE", f"/api/admin/discounts/{managed['id']}")[0], 403)

    def test_manager_revocation_during_request_is_rechecked_before_write(self):
        manager, manager_id = self.staff_account("manager")
        original = server.VeloraHandler.read_json

        def revoke_after_read(handler, *args, **kwargs):
            result = original(handler, *args, **kwargs)
            with self.app.connect() as connection:
                state = json.loads(connection.execute("SELECT data FROM commerce_state").fetchone()[0])
                state["staff"][str(manager_id)] = "warehouse"
                connection.execute("UPDATE commerce_state SET data=?", (json.dumps(state),))
            return result

        with mock.patch.object(server.VeloraHandler, "read_json", revoke_after_read):
            status = manager.request("POST", "/api/admin/discounts", {"code": "STALE", "name": "Stale permission", "theme": "custom", "type": "fixed", "amount": 10, "minSubtotal": 0, "startsAt": None, "endsAt": None, "active": True})[0]
        self.assertEqual(status, 403)
        self.assertEqual(self.admin.request("GET", "/api/admin/discounts")[1]["discounts"], [])

    def test_origin_and_csrf_protect_admin_mutations_and_public_quote_checks_origin(self):
        code = self.create()
        path = f"/api/admin/discounts/{code['id']}"
        self.assertEqual(self.admin.request("PATCH", path, {"active": False}, token=False)[0], 403)
        self.assertEqual(self.admin.request("PATCH", path, {"active": False}, origin=False)[0], 403)
        self.assertEqual(self.admin.request("DELETE", path, token=False)[0], 403)
        self.assertEqual(self.quote()[0], 200)
        self.assertEqual(self.public.request("POST", "/api/discounts/validate", {"code": code["code"], "items": [{"productId": "123456789abcdef0", "quantity": 1}]}, origin=False)[0], 403)
        self.assertEqual(self.public.request("GET", "/api/discounts/validate")[0], 405)

    def test_discount_survives_creator_deletion_without_exposing_account_data(self):
        code = self.create()
        with self.app.connect() as connection:
            connection.execute("DELETE FROM users WHERE email='admin@example.test'")
            self.assertIsNone(connection.execute("SELECT created_by FROM discount_codes WHERE id=?", (code["id"],)).fetchone()[0])
        status, result, _ = self.quote()
        self.assertEqual(status, 200, result)
        self.assertNotIn("admin@example.test", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
