from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


import logging

_logger = logging.getLogger(__name__)

class accountPublicSegment(models.Model):
    _name = "account.public.segment"

    name = fields.Char(string='Segment')
    code = fields.Char(string='Code')
    active = fields.Boolean(string='Active')
    account_segment_ids = fields.Many2many(
        'account.account',
         'account_account_segment_rel',
          'account_segment_id',
           'account_id', 
           string='Account Segment'
           )
    account_branch_ids = fields.Many2many(
        'multi.branch',
         'account_branch_segment_rel',
          'account_branch_id',
           'branch_id', 
           string='MDAs'
           )


class accountAccount(models.Model):
    _inherit = "account.account"

    account_segment_id = fields.Many2one('account.public.segment', string='Account Segment')

class accountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    code = fields.Char(string='Code')
    

class accountJournal(models.Model):
    _inherit = "account.journal"
    
    for_public_use = fields.Boolean(string="For Public user")
    code = fields.Char(
        string='Short Code',
        size=20, 
        required=True, 
        help="Shorter name used for display. The journal entries of this journal will also be named using this prefix by default.")
     
    def _get_internal_users_ids(self):
        Group = self.env['res.groups']
        group_roles = self.env.ref('ik_multi_branch.account_major_user').id
        users = Group.browse([group_roles]).users
        return users and users.ids or []
    
    def get_filtered_journal_record(self):
        view_id_form = self.env.ref('account.view_account_journal_form')
        view_id_tree = self.env.ref('account.view_account_journal_tree')
        view_id_kanban = self.env.ref('account.account_journal_dashboard_kanban_view')
        user = self.env.user
        allowed_internal_users = self._get_internal_users_ids()
        record_ids = []
        if user.id in allowed_internal_users: 
            return {
                'type': 'ir.actions.act_window',
                'name': _('Journals'),
                'res_model': 'account.journal',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': view_id_kanban.id,
                'views': [(view_id_kanban.id, 'kanban'), (view_id_tree.id, 'tree'), (view_id_form.id,'form')],
                'target': 'current',
                'domain': []
            }
        else:
            
            domain = [
                ('for_public_use', '=', False), 
                # ('branch_id', '=', user.branch_id.id),
                ('branch_id', 'in', user.branch_id.ids),
                # ('create_uid','=', user.id),
            ]
            non_user_journals = self.env['account.journal'].sudo().search(domain)
            record_ids = [res.id for res in non_user_journals]
            return {
                'type': 'ir.actions.act_window',
                'name': _('Journals'),
                'res_model': 'account.journal',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': view_id_kanban.id,
                'views': [(view_id_kanban.id, 'kanban'), (view_id_tree.id, 'tree'), (view_id_form.id,'form')],
                'target': 'current',
                'domain': [('id', 'in', record_ids)]
            } 
        
        
class AccountInvoice(models.Model):
    _inherit = 'account.move'
     
    @api.depends('company_id', 'invoice_filter_type_domain')
    def _compute_suitable_journal_ids(self):
        for m in self:
            journal_type = m.invoice_filter_type_domain or 'general'
            company_id = m.company_id.id or self.env.company.id
            Journals = self.env['account.journal'].sudo()
            account_major_user = (self.env.is_admin() or self.env.user.has_group('ik_multi_branch.account_major_user'))
            domain = [('company_id', '=', company_id), ('type', '=', journal_type)]
            branch_ids = [rec.id for rec in self.env.user.branch_ids if rec] + [self.env.user.branch_id.id]
            journal_ids = []
            for journal in Journals.search([]):
                journal_branches = [rec.id for rec in journal.allowed_branch_ids] + [journal.branch_id.id]
                if set(branch_ids).intersection(set(journal_branches)):
                    journal_ids.append(journal.id)
                 
                if journal.for_public_use:
                    journal_ids.append(journal.id)
            if account_major_user:
                domain = [
                ('company_id', '=', company_id),
                ('type', '=', journal_type),
                ]
            else:
                domain = [
                    ('company_id', '=', company_id),
                    ('type', '=', journal_type),
                    ('id', 'in', journal_ids)
                ]

            m.suitable_journal_ids = self.env['account.journal'].search(domain)

    external_memo_request = fields.Boolean('Is external memo request?')
    is_top_account_user = fields.Boolean('Is top account user?') #, compute="compute_top_account_user")
    partner_id = fields.Many2one(
        'res.partner',
        string='Beneficiary',
        readonly=True,
        tracking=True,
        states={'draft': [('readonly', False)]},
        inverse='_inverse_partner_id',
        check_company=True,
        change_default=True,
        ondelete='restrict',
    )
    # @api.depends('move_type')
    # def compute_top_account_user(self):
    #     for rec in self:
    #         if (self.env.is_admin() or self.env.user.has_group('ik_multi_branch.account_major_user')):
    #             rec.is_top_account_user = True
    #             rec.external_memo_request = False
    #         else:
    #             rec.is_top_account_user = False
    #             rec.external_memo_request = True

    # def check_budget_limit(self):
    #     # check analytic account - 
    #     # under budget lines, check the positions that contains the the selected chart of account and the budget line is on negative (for expenses)
    #     # if so, check the used amount on that line for that period,  if it exceeds, then raise a validationError.
    #     for rec in self.invoice_line_ids:
    #         _logger.info(rec.analytic_distribution)
    #         raise ValidationError(rec.analytic_distribution)

                
    def action_post(self):
        # self.check_budget_limit()
        account_major_user = (self.env.is_admin() or self.env.user.has_group('ik_multi_branch.account_major_user'))
        if self.external_memo_request and not account_major_user:
            raise ValidationError("Ops. You are not allowed confirm this Bill. Only Accountant General Group is responsible to do this.")
        res = super(AccountInvoice, self).action_post()
        return res
    
    def button_cancel(self):
        account_major_user = (self.env.is_admin() or self.env.user.has_group('ik_multi_branch.account_major_user'))
        if self.external_memo_request and not account_major_user:
            raise ValidationError("Ops. You are not allowed cancel this Bill. Only Accountant General Group is responsible to do this.")
        res = super(AccountInvoice, self).action_post()
        return res

