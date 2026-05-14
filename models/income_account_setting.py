# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class IncomeAccountSetting(models.Model):
    _name = 'income.account.setting'
    _description = 'Income Account Override Setting'

    name = fields.Char(default='Income Account Override Config')

    product_tmpl_ids = fields.Many2many(
        comodel_name='product.template',
        relation='income_account_setting_product_tmpl_rel',
        column1='setting_id',
        column2='product_tmpl_id',
        string='Products',
    )

    income_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Income Account',
        domain=[('account_type', '=', 'income')],
        ondelete='set null',
    )

    receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Receivable Account',
        domain=[('account_type', '=', 'asset_receivable')],
        ondelete='set null',
    )

    @api.model
    def _get_singleton(self):
        record = self.search([], limit=1)
        if not record:
            record = self.create({'name': 'Income Account Override Config'})
        return record

    @api.model
    def get_income_account_for_product(self, product_id):
        singleton = self._get_singleton()
        if not singleton.income_account_id:
            return False
        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            return False
        if product.product_tmpl_id in singleton.product_tmpl_ids:
            return singleton.income_account_id
        return False

    @api.model
    def get_receivable_account_for_product(self, product_id):
        singleton = self._get_singleton()
        if not singleton.receivable_account_id:
            return False
        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            return False
        if product.product_tmpl_id in singleton.product_tmpl_ids:
            return singleton.receivable_account_id
        return False

    @api.constrains('income_account_id', 'receivable_account_id')
    def _check_account_types(self):
        for record in self:
            if record.income_account_id and record.income_account_id.account_type != 'income':
                raise ValidationError(
                    _("Income Account must be an account of type 'Income'.")
                )
            if (
                record.receivable_account_id
                and record.receivable_account_id.account_type != 'asset_receivable'
            ):
                raise ValidationError(
                    _("Receivable Account must be an account of type 'Receivable'.")
                )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Store on the transient record itself so Odoo 18 onchange works correctly
    income_override_product_tmpl_ids = fields.Many2many(
        comodel_name='product.template',
        relation='res_config_income_override_product_rel',
        column1='config_id',
        column2='product_tmpl_id',
        string='Products',
    )

    income_override_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Income Account',
        domain=[('account_type', '=', 'income')],
    )

    income_override_receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Receivable Account',
        domain=[('account_type', '=', 'asset_receivable')],
    )

    @api.constrains('income_override_account_id', 'income_override_receivable_account_id')
    def _check_override_account_types(self):
        for record in self:
            if (
                record.income_override_account_id
                and record.income_override_account_id.account_type != 'income'
            ):
                raise ValidationError(
                    _("Income Account must be an account of type 'Income'.")
                )
            if (
                record.income_override_receivable_account_id
                and record.income_override_receivable_account_id.account_type != 'asset_receivable'
            ):
                raise ValidationError(
                    _("Receivable Account must be an account of type 'Receivable'.")
                )

    def set_values(self):
        super().set_values()
        singleton = self.env['income.account.setting']._get_singleton()
        singleton.write({
            'product_tmpl_ids': [(6, 0, self.income_override_product_tmpl_ids.ids)],
            'income_account_id': self.income_override_account_id.id or False,
            'receivable_account_id': self.income_override_receivable_account_id.id or False,
        })

    def get_values(self):
        res = super().get_values()
        singleton = self.env['income.account.setting']._get_singleton()
        res.update({
            'income_override_product_tmpl_ids': [(6, 0, singleton.product_tmpl_ids.ids)],
            'income_override_account_id': singleton.income_account_id.id or False,
            'income_override_receivable_account_id': singleton.receivable_account_id.id or False,
        })
        return res
