from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CompanyMemo(models.Model):
    _inherit = "memo.model"

    company_id = fields.Many2one(
        'res.company', 
        default=lambda s: s.env.user.company_id.id,
        string='Company'
        )
    
    branch_id = fields.Many2one('multi.branch', string='MDA Sector',
                                default=lambda self: self.env.user.branch_id.id, required=False)
    partner_id = fields.Many2one('res.partner', string='Partner',
                                default=lambda self: self.env.user.partner_id.id)
    
    external_memo_request = fields.Boolean(string='External request')
    
    
     