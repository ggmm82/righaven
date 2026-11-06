"""Exercise management calls against the actual native administrator guard.

Extracting the small guard and handlers keeps this regression runnable without
installing the Gateway's model/database stack; native HTTP is tested in Compose.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from fastapi import HTTPException


class ManagementAuthorizationContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'core/backend/app/gateway'
        guard=next(n for n in ast.parse((root/'deps.py').read_text()).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='require_admin_user')
        names={'list_assignable_roles','create_account','manage_account_credentials'}
        routes=[n for n in ast.parse((root/'routers/admin_users.py').read_text()).body if isinstance(n,ast.AsyncFunctionDef) and n.name in names]
        for node in routes:node.decorator_list=[]
        async def admin(request):return request.system_role=='admin'
        self.namespace={'is_admin_user':admin,'HTTPException':HTTPException,'assignable_role_names':lambda:{'admin','user'},'Depends':lambda value:None,'get_user_repository':lambda:None}
        module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),guard,*routes],type_ignores=[])
        exec(compile(ast.fix_missing_locations(module),'<native management authorization>','exec'),self.namespace)

    async def test_non_admin_is_denied_before_any_account_or_credential_mutation(self):
        request=SimpleNamespace(system_role='user')
        for name,args in [('list_assignable_roles',[request]),('create_account',[None,request]),('manage_account_credentials',[None,None,request,None])]:
            with self.subTest(handler=name),self.assertRaises(HTTPException) as caught:
                await self.namespace[name](*args)
            self.assertEqual(caught.exception.status_code,403)

    async def test_admin_can_read_configured_roles_through_native_guard(self):
        response=await self.namespace['list_assignable_roles'](SimpleNamespace(system_role='admin'))
        self.assertEqual(response,{'roles':['admin','user']})


if __name__=='__main__':unittest.main()
