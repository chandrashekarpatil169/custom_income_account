# -*- coding: utf-8 -*-
{
    'name': 'Custom Product Income Account',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Select products + one income account in Accounting Settings; auto-overrides on invoices.',
    'author': 'Custom',
    'depends': ['account', 'product','sale_management','accountant','stock','purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
