# models/invoice_entry.py
# Main model to store uploaded invoices and generate accounting entries.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from lxml import etree
import base64

class InvoiceEntry(models.Model):
    """Model used to upload invoice documents and create minimal journal entries."""

    _name = 'invoice.entry'
    _description = 'Uploaded Invoice'

    # Basic information
    name = fields.Char(string='Description', default='New Invoice')
    file = fields.Binary(string='Invoice File', attachment=True, required=True,
                         help='Upload the XML or PDF invoice file.')
    file_name = fields.Char(string='File Name')

    # Computed invoice type based on the uploaded XML data
    invoice_type = fields.Selection([
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit'),
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit'),
    ], string='Invoice Type', compute='_compute_invoice_type', store=True)

    # Link to the generated account.move
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('processed', 'Processed')
    ], default='draft', string='Status')

    @api.depends('file')
    def _compute_invoice_type(self):
        """Detect the invoice type from the uploaded XML file."""
        for entry in self:
            entry.invoice_type = False
            if not entry.file:
                continue
            try:
                xml_root = etree.fromstring(base64.b64decode(entry.file))
            except Exception:
                # Cannot parse XML -> default to vendor bill
                entry.invoice_type = 'in_invoice'
                continue
            # Determine if this is an invoice or credit note
            inv_type = 'invoice'
            if xml_root.tag.endswith('CreditNote'):
                inv_type = 'refund'
            # Compare the VAT numbers to know if we are supplier or customer
            vat = (entry.env.company.vat or '').replace(' ', '').upper()
            supplier_vat = xml_root.findtext('.//{*}AccountingSupplierParty//{*}CompanyID')
            customer_vat = xml_root.findtext('.//{*}AccountingCustomerParty//{*}CompanyID')
            supplier_vat = (supplier_vat or '').replace(' ', '').upper()
            customer_vat = (customer_vat or '').replace(' ', '').upper()
            if vat and vat == supplier_vat:
                entry.invoice_type = f'out_{inv_type}'
            elif vat and vat == customer_vat:
                entry.invoice_type = f'in_{inv_type}'
            else:
                # Fallback to vendor bill
                entry.invoice_type = f'in_{inv_type}'

    def action_process(self):
        """Create a journal entry from the uploaded file."""
        for entry in self:
            if not entry.file:
                raise UserError(_('Please upload an invoice file.'))
            # Create an attachment linked to this entry
            attachment = entry.env['ir.attachment'].create({
                'name': entry.file_name or 'invoice',
                'datas': entry.file,
                'res_model': 'invoice.entry',
                'res_id': entry.id,
            })
            entry.state = 'processed'
            # Choose journal according to invoice type
            move_type = entry.invoice_type or 'in_invoice'
            journal_type = 'sale' if move_type.startswith('out_') else 'purchase'
            journal = entry.env['account.journal'].search([
                ('type', '=', journal_type),
            ], limit=1)
            if not journal:
                raise UserError(_('No journal found for type %s') % journal_type)
            # Create the account.move using Odoo's helper
            move = journal.with_context(default_move_type=move_type)._create_document_from_attachment(attachment.id)
            entry.move_id = move.id
            # Attach the uploaded file to the created move as well
            attachment.write({'res_model': 'account.move', 'res_id': move.id})
        return True
