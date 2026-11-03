"""Integration checks for stock reservations, fulfillment, returns and staff boundaries."""
import json
import unittest
from datetime import datetime, timezone, timedelta
import test_catalog_server as catalog_tests
from test_auth_server import Client, PASSWORD
import server

class CommerceTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__['setUpClass']
    setUp = catalog_tests.CatalogServerTests.setUp
    tearDown = catalog_tests.CatalogServerTests.tearDown

    def state(self):
        status, data, _ = self.admin.request('GET', '/api/admin/commerce')
        self.assertEqual(status, 200, data)
        return data

    def change(self, action, **payload):
        return self.admin.request('POST', '/api/admin/commerce', {'revision':self.state()['revision'], 'action':action, **payload})

    def seed(self):
        self.customer = Client(self.app)
        self.assertEqual(self.customer.register()[0], 201)
        customer_id = self.customer.request('GET','/api/auth/me')[1]['user']['id']
        self.assertEqual(self.change('variant',product='123456789abcdef0',size='M',color='Blue',location='Main warehouse',stock=5,threshold=2,target=10,lot='Spring')[0],200)
        return customer_id,self.state()['variants'][0]['id']

    def test_reserve_partial_ship_return_and_duplicate_protection(self):
        customer,variant=self.seed()
        self.assertEqual(self.change('order',customer=customer,address='Test street 1',lines=[{'variant':variant,'quantity':3}])[0],200)
        state=self.state();o=state['orders'][0];line=o['lines'][0]['id']
        self.assertEqual(state['variants'][0]['stock'],2)
        self.assertEqual(self.change('ship',order=o['id'],line=line,quantity=1,tracking='Test carrier A')[0],200)
        self.assertEqual(self.state()['orders'][0]['status'],'processing')
        self.assertEqual(self.change('deliver',order=o['id'])[0],400)
        self.assertEqual(self.change('ship',order=o['id'],line=line,quantity=2,tracking='Test carrier B')[0],200)
        self.assertEqual(self.change('deliver',order=o['id'])[0],200)
        payload=dict(order=o['id'],line=line,quantity=2,condition='unworn',resolution='refund',reason='Sizing')
        self.assertEqual(self.change('return',**payload)[0],200)
        self.assertEqual(self.state()['variants'][0]['stock'],4)
        self.assertEqual(self.change('return',**payload)[0],400)
        self.assertEqual(self.state()['variants'][0]['stock'],4)
        # Catalog stock is kept in sync.
        catalog=self.public.request('GET','/api/catalog')[1]['products'][0]
        self.assertEqual(catalog['stock'],4)

    def test_atomic_oversell_stale_revision_and_authorization(self):
        customer,v=self.seed()
        before=self.state()
        self.assertEqual(self.change('order',customer=customer,address='Test',lines=[{'variant':v,'quantity':3},{'variant':v,'quantity':3}])[0],400)
        self.assertEqual(self.state()['variants'][0]['stock'],5)
        self.assertEqual(len(self.state()['orders']),0)
        self.assertEqual(self.admin.request('POST','/api/admin/commerce',{'action':'location','name':'Store','revision':-1})[0],409)
        self.assertEqual(self.public.request('GET','/api/admin/commerce')[0],401)
        self.assertEqual(self.customer.request('GET','/api/admin/commerce')[0],403)
        self.assertEqual(self.admin.request('POST','/api/admin/commerce',{'action':'location','name':'Store','revision':before['revision']},token=False)[0],403)

    def test_warehouse_and_manager_permissions(self):
        with self.app.connect() as c:
            c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",('Staff','staff@example.test',self.password_hash,server.now_iso()))
            staff_id=c.execute("SELECT id FROM users WHERE email='staff@example.test'").fetchone()[0]
        staff=Client(self.app);self.assertEqual(staff.login(email='staff@example.test')[0],200)
        self.assertEqual(self.change('staff',user=staff_id,role='warehouse')[0],200)
        for path in ['/api/admin/products','/api/admin/customers','/api/admin/security','/api/admin/business-details']:
            self.assertEqual(staff.request('GET',path)[0],403,path)
        payload=staff.request('GET','/api/admin/commerce')[1]
        self.assertNotIn('customers',payload);self.assertNotIn('staff',payload)
        self.assertEqual(staff.request('POST','/api/admin/commerce',{'action':'bulk','revision':payload['revision']})[0],403)
        self.assertEqual(self.change('staff',user=staff_id,role='manager')[0],200)
        self.assertEqual(staff.request('GET','/api/admin/products')[0],200)
        self.assertEqual(staff.request('GET','/api/admin/security')[0],403)

    def test_expired_return_and_exchange(self):
        customer,v=self.seed()
        self.change('order',customer=customer,address='Test',lines=[{'variant':v,'quantity':1}])
        o=self.state()['orders'][0];line=o['lines'][0]['id']
        self.change('ship',order=o['id'],line=line,quantity=1,tracking='Carrier')
        self.change('deliver',order=o['id'])
        self.assertEqual(self.change('return',order=o['id'],line=line,quantity=1,condition='unworn',resolution='exchange',replacement=v,reason='Swap')[0],200)
        state=self.state();self.assertEqual(len(state['orders']),2);self.assertEqual(state['orders'][1]['status'],'incoming');self.assertNotIn('deliveredAt',state['orders'][1])
        exchange=state['orders'][1];self.change('ship',order=exchange['id'],line=exchange['lines'][0]['id'],quantity=1,tracking='Again');self.change('deliver',order=exchange['id'])
        with self.app.connect() as c:
            s=json.loads(c.execute('SELECT data FROM commerce_state').fetchone()[0]);s['orders'][1]['deliveredAt']=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat();c.execute('UPDATE commerce_state SET data=?',(json.dumps(s),))
        self.assertEqual(self.change('return',order=exchange['id'],line=exchange['lines'][0]['id'],quantity=1,condition='unworn',resolution='refund',reason='Late')[0],400)

    def test_bulk_guides_and_legacy_stock_guard(self):
        _,v=self.seed()
        self.assertEqual(self.change('bulk',products=['123456789abcdef0'],price=199.95,published=True,tag='Summer sale')[0],200)
        self.assertEqual(self.change('guide',product='123456789abcdef0',guide='M: chest 96 cm')[0],200)
        p=self.public.request('GET','/api/catalog')[1]['products'][0]
        self.assertEqual(p['size_guide'],'M: chest 96 cm')
        self.assertEqual(p['discount_tag'],'Summer sale')
        self.assertEqual(p['variant_stock']['blue|m'],5)
        self.assertEqual(p['price'],199.95)
        self.assertEqual(self.admin.request('PATCH','/api/admin/products/123456789abcdef0',{'stock':99})[0],409)
        self.assertEqual(self.change('bulk',products=['123456789abcdef0'],price=None,published=False,tag='Summer')[0],200)
        self.assertEqual(self.public.request('GET','/api/catalog')[1]['products'],[])

    def test_invalid_inputs_do_not_mutate(self):
        self.seed()
        revision=self.state()['revision']
        for payload in [{'action':[]},{'action':'variant','product':[]},{'action':'staff','user':[]},{'action':'bulk','products':[{}]},{'action':'order','customer':1,'address':'Test','lines':[None]}]:
            self.assertEqual(self.admin.request('POST','/api/admin/commerce',{'revision':revision,**payload})[0],400)
        self.assertEqual(self.state()['revision'],revision)

if __name__=='__main__':unittest.main()
