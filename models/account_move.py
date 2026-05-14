# -*- coding: utf-8 -*-
from odoo import models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_computed_account(self):
        """Override income (credit) account for mapped products on customer invoices."""
        account = super()._get_computed_account()
        if self.move_id.move_type not in ('out_invoice', 'out_refund'):
            return account
        if not self.product_id:
            return account
        override = self.env['income.account.setting'].get_income_account_for_product(
            self.product_id.id
        )
        return override if override else account

    @api.onchange('product_id')
    def _onchange_product_id_income_override(self):
        if not self.product_id:
            return
        if self.move_id.move_type not in ('out_invoice', 'out_refund'):
            return
        override = self.env['income.account.setting'].get_income_account_for_product(
            self.product_id.id
        )
        if override:
            self.account_id = override


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        Setting = self.env['income.account.setting']

        # ── BEFORE posting: override income lines (draft = writable) ─────────
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            for line in move.invoice_line_ids.filtered(
                lambda l: l.product_id and l.display_type == 'product'
            ):
                income_override = Setting.get_income_account_for_product(line.product_id.id)
                if income_override:
                    line.with_context(check_move_validity=False).account_id = income_override.id

        # Collect split plan before posting
        split_plan = {}
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            singleton = Setting._get_singleton()
            if not singleton.receivable_account_id:
                continue
            # Split based on line totals (including taxes) so receivable split
            # matches journal items and financial reports.
            mapped_amt = sum(
                abs(l.price_total)
                for l in move.invoice_line_ids.filtered(
                    lambda l: l.product_id and l.display_type == 'product'
                )
                if Setting.get_income_account_for_product(l.product_id.id)
            )
            unmapped_amt = sum(
                abs(l.price_total)
                for l in move.invoice_line_ids.filtered(
                    lambda l: l.product_id and l.display_type == 'product'
                )
                if not Setting.get_income_account_for_product(l.product_id.id)
            )
            if mapped_amt == 0:
                continue
            split_plan[move.id] = {
                'mapped': mapped_amt,
                'unmapped': unmapped_amt,
                'custom_account_id': singleton.receivable_account_id.id,
            }

        # ── POST ──────────────────────────────────────────────────────────────
        result = super()._post(soft=soft)

        # ── AFTER posting: fix receivable via SQL ─────────────────────────────
        if not split_plan:
            return result

        cr = self.env.cr

        # Get all column names at runtime — works on any Odoo version
        cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'account_move_line'
            ORDER BY ordinal_position
        """)
        all_cols = [r[0] for r in cr.fetchall()]
        skip_cols = {'id', 'create_uid', 'create_date', 'write_uid', 'write_date'}
        copy_cols = [c for c in all_cols if c not in skip_cols]

        for move in self:
            plan = split_plan.get(move.id)
            if not plan:
                continue

            mapped_amt = plan['mapped']
            unmapped_amt = plan['unmapped']
            custom_account_id = plan['custom_account_id']
            total_amt = mapped_amt + unmapped_amt
            is_refund = move.move_type == 'out_refund'
            line_label = move.name or move.payment_reference or move.ref or '/'
            line_ref = move.ref or move.payment_reference or move.name or '/'

            # Get the receivable line Odoo just created
            cr.execute("""
                SELECT aml.id, aml.debit, aml.credit, aml.amount_currency
                FROM account_move_line aml
                JOIN account_account aa ON aa.id = aml.account_id
                WHERE aml.move_id = %s AND aa.account_type = 'asset_receivable'
                LIMIT 1
            """, [move.id])
            row = cr.fetchone()
            if not row:
                continue

            rec_id, rec_debit, rec_credit, rec_currency = row
            total_receivable = rec_debit if not is_refund else rec_credit

            if unmapped_amt == 0:
                # All mapped — simple redirect
                cr.execute(
                    """
                    UPDATE account_move_line
                    SET account_id = %s,
                        name = %s,
                        ref = %s
                    WHERE id = %s
                    """,
                    [custom_account_id, line_label, line_ref, rec_id]
                )
            else:
                # Split receivable into two lines
                ratio = mapped_amt / total_amt
                mapped_rec = round(total_receivable * ratio, 2)
                unmapped_rec = round(total_receivable - mapped_rec, 2)
                mapped_cur = round(abs(rec_currency) * ratio, 2)
                unmapped_cur = round(abs(rec_currency) - mapped_cur, 2)

                # Resize existing line → unmapped portion, keep default account
                if is_refund:
                    unmapped_balance = -unmapped_rec
                    unmapped_residual_cur = -unmapped_cur
                    cr.execute("""
                        UPDATE account_move_line
                        SET credit=%s,
                            debit=0,
                            balance=%s,
                            amount_currency=%s,
                            amount_residual=%s,
                            amount_residual_currency=%s,
                            name=%s,
                            ref=%s
                        WHERE id=%s
                    """, [
                        unmapped_rec,
                        unmapped_balance,
                        unmapped_residual_cur,
                        unmapped_balance,
                        unmapped_residual_cur,
                        line_label,
                        line_ref,
                        rec_id
                    ])
                else:
                    unmapped_balance = unmapped_rec
                    cr.execute("""
                        UPDATE account_move_line
                        SET debit=%s,
                            credit=0,
                            balance=%s,
                            amount_currency=%s,
                            amount_residual=%s,
                            amount_residual_currency=%s,
                            name=%s,
                            ref=%s
                        WHERE id=%s
                    """, [
                        unmapped_rec,
                        unmapped_balance,
                        unmapped_cur,
                        unmapped_balance,
                        unmapped_cur,
                        line_label,
                        line_ref,
                        rec_id
                    ])

                # Clone the row, override only account_id + amounts
                select_exprs = []
                for col in copy_cols:
                    if col in (
                        'account_id',
                        'debit',
                        'credit',
                        'balance',
                        'amount_currency',
                        'amount_residual',
                        'amount_residual_currency',
                        'name',
                        'ref',
                        'parent_state',
                        'move_name',
                    ):
                        select_exprs.append('%s')
                    else:
                        select_exprs.append(col)

                debit_val = 0.0 if is_refund else mapped_rec
                credit_val = mapped_rec if is_refund else 0.0
                balance_val = debit_val - credit_val
                currency_val = -mapped_cur if is_refund else mapped_cur

                sql = f"""
                    INSERT INTO account_move_line ({', '.join(copy_cols)})
                    SELECT {', '.join(select_exprs)}
                    FROM account_move_line
                    WHERE id = %s
                """
                # params order must match select_exprs — one %s per overridden col
                params = []
                for col in copy_cols:
                    if col == 'account_id':
                        params.append(custom_account_id)
                    elif col == 'debit':
                        params.append(debit_val)
                    elif col == 'credit':
                        params.append(credit_val)
                    elif col == 'amount_currency':
                        params.append(currency_val)
                    elif col == 'balance':
                        params.append(balance_val)
                    elif col == 'amount_residual':
                        params.append(balance_val)
                    elif col == 'amount_residual_currency':
                        params.append(currency_val)
                    elif col == 'name':
                        params.append(line_label)
                    elif col == 'ref':
                        params.append(line_ref)
                    elif col == 'parent_state':
                        params.append('posted')
                    elif col == 'move_name':
                        params.append(move.name or '/')
                params.append(rec_id)  # WHERE id = %s
                cr.execute(sql, params)

        self.env['account.move.line'].invalidate_model()
        self.env['account.move'].invalidate_model()

        return result
