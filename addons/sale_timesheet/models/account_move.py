# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.osv import expression


class AccountMove(models.Model):
    _inherit = "account.move"

    timesheet_ids = fields.One2many('account.analytic.line', 'timesheet_invoice_id', string='Timesheets', readonly=True, copy=False)
    timesheet_count = fields.Integer("Number of timesheets", compute='_compute_timesheet_count')

    @api.depends('timesheet_ids')
    def _compute_timesheet_count(self):
        timesheet_data = self.env['account.analytic.line'].read_group([('timesheet_invoice_id', 'in', self.ids)], ['timesheet_invoice_id'], ['timesheet_invoice_id'])
        mapped_data = dict([(t['timesheet_invoice_id'][0], t['timesheet_invoice_id_count']) for t in timesheet_data])
        for invoice in self:
            invoice.timesheet_count = mapped_data.get(invoice.id, 0)

    def action_view_timesheet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Timesheets'),
            'domain': [('project_id', '!=', False)],
            'res_model': 'account.analytic.line',
            'view_id': False,
            'view_mode': 'tree,form',
            'help': _("""
                <p class="o_view_nocontent_smiling_face">
                    Record timesheets
                </p><p>
                    You can register and track your workings hours by project every
                    day. Every time spent on a project will become a cost and can be re-invoiced to
                    customers if required.
                </p>
            """),
            'limit': 80,
            'context': {
                'default_project_id': self.id,
                'search_default_project_id': [self.id]
            }
        }

    def _link_timesheets_to_invoice(self, date=None):
        """ Search timesheets and link this timesheets to the invoice

            When we create an invoice from a sale order, we need to
            link the timesheets in this sale order to the invoice.
            Then, we can know which timesheets are invoiced in the sale order.

            :param date: All timesheets on task before or equals this date
                        in the sale order are invoiced.
        """
        for line in self.filtered(lambda i: i.type == 'out_invoice' and i.state == 'draft').invoice_line_ids:
            sale_line_delivery = line.sale_line_ids.filtered(lambda sol: sol.product_id.invoice_policy == 'delivery' and sol.product_id.service_type == 'timesheet')
            if sale_line_delivery:
                domain = line._timesheet_domain_get_invoiced_lines(sale_line_delivery)
                if date:
                    domain = expression.AND([domain, [('date', '<=', date)]])
                timesheets = self.env['account.analytic.line'].sudo().search(domain)
                timesheets.write({'timesheet_invoice_id': line.move_id.id})


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _timesheet_domain_get_invoiced_lines(self, sale_line_delivery):
        """ Get the domain for the timesheet to link to the created invoice
            :param sale_line_delivery: recordset of sale.order.line to invoice
            :return a normalized domain
        """
        return [
            ('so_line', 'in', sale_line_delivery.ids),
            ('project_id', '!=', False),
            '|', ('timesheet_invoice_id', '=', False), ('timesheet_invoice_id.state', '=', 'cancel')
        ]
