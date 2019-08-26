# -*- coding: utf-8 -*-
{
    'name': "financiera_bna_debito_automatico",

    'summary': """
        Barrido de debito en cuenta de cliente de BNA.""",

    'description': """
        Aplicacion de generacion de archivo para cobro de cuotas
        mediante debito en cuenta de BNA. Y carga de archivo resultado
        para cobro de dichas cuotas.
    """,

    'author': "Librasoft",
    'website': "https://libra-soft.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'finance',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'financiera_prestamos'],

    # always loaded
    'data': [
        'security/user_groups.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/views.xml',
        'views/extends_financiera_prestamo_cuota.xml',
        'wizards/financiera_bna_cobrar_wizard.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}