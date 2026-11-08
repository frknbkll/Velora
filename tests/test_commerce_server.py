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
        self.assertEqual(self.admin.request('PATCH','/api/admin/products/123456789abcdef0',{'base_color':'Blue'})[0],200)
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
        status,result,_=self.admin.request('POST','/api/admin/colleagues',{'firstName':'Staff','lastName':'Example','email':'staff@velora.com','password':PASSWORD,'active':True,'department':'commerce','role':'warehouse','fullControl':False,'grants':[]})
        self.assertEqual(status,201,result)
        staff_id=result['colleague']['id']
        staff=Client(self.app);self.assertEqual(staff.login(email='staff@velora.com')[0],200)
        for path in ['/api/admin/products','/api/admin/customers','/api/admin/security','/api/admin/business-details']:
            self.assertEqual(staff.request('GET',path)[0],403,path)
        payload=staff.request('GET','/api/admin/commerce')[1]
        self.assertNotIn('customers',payload);self.assertNotIn('staff',payload)
        self.assertEqual(staff.request('POST','/api/admin/commerce',{'action':'bulk','revision':payload['revision']})[0],403)
        self.assertEqual(self.admin.request('PATCH',f'/api/admin/colleagues/{staff_id}',{'active':True,'department':'commerce','role':'manager','fullControl':False,'grants':[]})[0],200)
        self.assertEqual(staff.login(email='staff@velora.com')[0],200)
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

    def test_inventory_only_accepts_selectable_product_options_atomically(self):
        self.seed()
        before=self.state()
        for changes in ({'size':'TYPO SIZE'},{'color':'Not a product color'}):
            status,data,_=self.change('variant',product='123456789abcdef0',size=changes.get('size','M'),color=changes.get('color','Blue'),location='Main warehouse',stock=99,threshold=2,target=10)
            self.assertEqual(status,400,data)
            self.assertIn('listed for this product',data['error'])
            self.assertEqual(self.state()['variants'],before['variants'])
            self.assertEqual(self.state()['revision'],before['revision'])
            self.assertEqual(self.public.request('GET','/api/catalog')[1]['products'][0]['stock'],5)
        self.assertEqual(self.change('variant',product='123456789abcdef0',size='m',color='bLuE',location='Main warehouse',stock=6,threshold=2,target=10)[0],200)
        updated=self.state()['variants'][0]
        self.assertEqual((updated['size'],updated['color']),('M','Blue'))
        self.assertEqual((updated['id'],updated['sku']), (before['variants'][0]['id'],before['variants'][0]['sku']))

    def test_preset_and_custom_colors_match_storefront_options(self):
        mapping={'assets/first.png':[{'name':'Sand','hex':'#cccccc','image':'assets/first.png'},{'name':'Navy','hex':'#222244','image':'assets/second.png'}]}
        (self.root/'product-color-images.js').write_text('window.veloraColorImages = '+json.dumps(mapping)+';',encoding='utf-8')
        options=self.state()['variantOptions']['123456789abcdef0']
        self.assertEqual(options['colors'],['Sand','Navy'])
        self.assertEqual(self.change('variant',product='123456789abcdef0',size='M',color='navy',location='Main warehouse',stock=3,threshold=2,target=10)[0],200)
        self.assertEqual(self.public.request('GET','/api/catalog')[1]['products'][0]['variant_stock']['navy|m'],3)
        self.assertEqual(self.admin.request('POST','/api/admin/products/123456789abcdef0/colors',{'name':'Rose','hex':'#cc8877','image':'assets/third.png'})[0],201)
        self.assertEqual(self.state()['variantOptions']['123456789abcdef0']['colors'],['Sand','Navy','Rose'])
        self.assertEqual(self.change('variant',product='123456789abcdef0',size='M',color='Rose',location='Main warehouse',stock=2,threshold=2,target=10)[0],200)

    def test_product_edits_cannot_detach_available_or_reserved_inventory(self):
        customer,variant=self.seed()
        before=self.state()['variants'][0]
        for patch in ({'sizes':['S','L']},{'base_color':'Green'}):
            status,data,_=self.admin.request('PATCH','/api/admin/products/123456789abcdef0',patch)
            self.assertEqual(status,409,data)
            self.assertEqual(self.state()['variants'][0],before)
        self.assertEqual(self.admin.request('PATCH','/api/admin/products/123456789abcdef0',{'base_color':'BLUE','name':'Case-only edit'})[0],200)
        self.assertEqual(self.public.request('GET','/api/catalog')[1]['products'][0]['variant_stock']['blue|m'],5)
        self.assertEqual(self.change('order',customer=customer,address='Test',lines=[{'variant':variant,'quantity':5}])[0],200)
        self.assertEqual(self.admin.request('PATCH','/api/admin/products/123456789abcdef0',{'base_color':'Green'})[0],409)

    def test_legacy_staff_editor_cannot_change_roles_or_grant_full_control(self):
        status,result,_=self.admin.request('POST','/api/admin/colleagues',{'firstName':'Store','lastName':'Manager','email':'manager@velora.com','password':PASSWORD,'active':True,'department':'commerce','role':'manager','fullControl':False,'grants':[]})
        self.assertEqual(status,201,result)
        staff_id=result['colleague']['id']
        before=self.state()
        status,data,_=self.change('staff',user=staff_id,role='owner')
        self.assertEqual(status,409,data)
        self.assertIn('Velora Accounts',data['error'])
        self.assertEqual(self.state()['revision'],before['revision'])
        account=self.admin.request('GET','/api/admin/colleagues')[1]['colleagues'][0]
        self.assertEqual((account['role'],account['fullControl']),('manager',False))
        manager=Client(self.app);self.assertEqual(manager.login(email='manager@velora.com')[0],200)
        self.assertEqual(manager.request('GET','/api/intranet/folders/finance/files')[0],403)
        self.assertEqual(manager.request('POST','/api/admin/commerce',{'action':'staff','user':staff_id,'role':'owner','revision':before['revision']})[0],403)

    def test_delivered_expired_orders_do_not_lock_catalog_options_or_restock_hidden_stock(self):
        customer,variant=self.seed()
        self.assertEqual(self.change('order',customer=customer,address='Test',lines=[{'variant':variant,'quantity':5}])[0],200)
        order=self.state()['orders'][0];line=order['lines'][0]['id']
        self.assertEqual(self.change('ship',order=order['id'],line=line,quantity=5,tracking='Carrier')[0],200)
        self.assertEqual(self.change('deliver',order=order['id'])[0],200)
        self.assertEqual(self.admin.request('PATCH','/api/admin/products/123456789abcdef0',{'base_color':'Green'})[0],409)
        with self.app.connect() as connection:
            state=json.loads(connection.execute('SELECT data FROM commerce_state WHERE id=1').fetchone()[0])
            state['orders'][0]['deliveredAt']=(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()
            connection.execute('UPDATE commerce_state SET data=? WHERE id=1',(json.dumps(state),))
        status,result,_=self.admin.request('PATCH','/api/admin/products/123456789abcdef0',{'base_color':'Green'})
        self.assertEqual(status,200,result)
        self.assertEqual(self.change('return',order=order['id'],line=line,quantity=1,condition='unworn',resolution='refund',reason='Expired')[0],400)
        self.assertEqual(self.state()['variants'][0]['stock'],0)
        self.assertEqual(self.state()['orders'][0]['lines'][0]['color'],'Blue')
        self.assertEqual(self.change('retire-variant',variant=variant)[0],200)
        self.assertEqual(self.change('return',order=order['id'],line=line,quantity=1,condition='unworn',resolution='refund',reason='Still expired')[0],400)
        self.assertEqual(self.public.request('GET','/api/catalog')[1]['products'][0]['stock'],0)

    def test_legacy_invalid_stock_has_an_explicit_atomic_cleanup_path(self):
        self.seed()
        with self.app.connect() as connection:
            state=json.loads(connection.execute('SELECT data FROM commerce_state WHERE id=1').fetchone()[0])
            state['variants'].append({**state['variants'][0],'id':'obsolete-stock','color':'TYPO COLOR','size':'TYPO SIZE','stock':4})
            connection.execute('UPDATE commerce_state SET data=? WHERE id=1',(json.dumps(state),))
            connection.execute('UPDATE products SET stock=9 WHERE id=?',('123456789abcdef0',))
        before=self.state()
        self.assertEqual(self.change('retire-variant',variant=before['variants'][0]['id'])[0],400)
        self.assertEqual(self.state()['revision'],before['revision'])
        self.assertEqual(self.change('retire-variant',variant='obsolete-stock')[0],200)
        self.assertEqual(self.state()['variants'],[before['variants'][0]])
        self.assertEqual(self.public.request('GET','/api/catalog')[1]['products'][0]['stock'],5)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM product_activity WHERE action='inventory cleanup'").fetchone()[0],1)

    def test_invalid_stock_cleanup_cannot_remove_pending_order_or_return_mapping(self):
        customer,variant=self.seed()
        self.assertEqual(self.change('order',customer=customer,address='Test',lines=[{'variant':variant,'quantity':5}])[0],200)
        with self.app.connect() as connection:
            state=json.loads(connection.execute('SELECT data FROM commerce_state WHERE id=1').fetchone()[0])
            state['variants'][0]['color']='Legacy typo'
            connection.execute('UPDATE commerce_state SET data=? WHERE id=1',(json.dumps(state),))
        before=self.state()
        self.assertEqual(self.change('retire-variant',variant=variant)[0],409)
        self.assertEqual(self.state()['variants'],before['variants'])
        self.assertEqual(self.state()['revision'],before['revision'])

if __name__=='__main__':unittest.main()
