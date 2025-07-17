# __manifest__.py
# Module metadata and minimal dependencies for our invoice upload module.
{
    'name': 'Invoice Upload',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Simple upload of incoming and outgoing invoices with auto posting',
    'description': 'Upload invoices as attachments and generate minimal journal entries.',
    'depends': ['base', 'account', 'account_edi', 'account_edi_ubl_cii'],
    'data': [
        'security/ir.model.access.csv',
        'views/invoice_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
