from odoo import models, fields, api, _
from odoo.exceptions import ValidationError 


class Forward_Wizard(models.TransientModel):
    _name = "memo.foward"

    resp = fields.Many2one('res.users', 'Current Sender')
    memo_record = fields.Many2one('memo.model','Memo Reference',)
    description_two = fields.Text('Comment')
    date = fields.Datetime('Date', default=lambda self: fields.datetime.now())#, default=fields.Datetime.now())
    direct_employee_id = fields.Many2one('hr.employee', 'Direct To')
    next_stage_id = fields.Many2one('memo.stage', 'Next stage')
    is_approver = fields.Selection([('yes', 'Yes'),('no', 'No')],default="", string="Is Approver")
    users_followers = fields.Many2many('hr.employee', string='Add followers')
    is_officer = fields.Boolean(string="Is Officer", help="Checks if the current user is a normal officer")
    is_approver_stage = fields.Boolean(string="Is Approval stage", help="Used to determine if the last one is approver stage")
    all_superior_ids = fields.Many2many('hr.employee',string="Employees for approvals",compute="_load_all_superior_ids") 

    def get_next_stage_artifact(self):
        approver_ids, next_stage_id = self.memo_record.get_next_stage_artifact(self.memo_record.stage_id, False)
        return approver_ids, next_stage_id
          
    def _get_all_related_superior_ids(self):
        approver_ids, next_stage_id= self.get_next_stage_artifact()
        return approver_ids
      
    @api.depends("memo_record")
    def _load_all_superior_ids(self):
        self.all_superior_ids = [(6,0, self._get_all_related_superior_ids())]
 
    def forward_memo(self): # Always available, 
        if self.memo_record.memo_type.memo_key == "Payment":
            if self.memo_record.amountfig < 0:
                raise ValidationError('If you are running a payment Memo, kindly ensure the amount is \
                    greater than 0')
        msg = "No Comment"
        if self.description_two:
            msg = self.description_two
        if self.direct_employee_id:
            body = "</br><b>{}:</b> {}</br>".format(self.env.user.name, self.description_two if self.description_two else "-")
            memo = self.env['memo.model'].sudo().search([('id', '=', self.memo_record.id)])
            comment_msg = " "
            if memo.comments:
                comment_msg = memo.comments if memo.comments else "-"
            memo.write({
                    'res_users': [(4, self.env.uid)],
                    'set_staff': self.direct_employee_id.id, 'direct_employee_id': self.direct_employee_id.id, 'state': 'Sent',
                    'users_followers': [(4, self.direct_employee_id.id)],
                    'approver_id': self.direct_employee_id.id if self.is_approver == "yes" else False,
                    'comments': comment_msg +' '+body,
                    }) 
            memo.message_post(body=body)
            # return{'type': 'ir.actions.act_window_close'}
        else:
            raise ValidationError('Please select an Employee to Direct To')
        next_stage_id = self.get_next_stage_artifact()
        return self.memo_record.confirm_memo(self.direct_employee_id.name, msg)#, next_stage_id[1])
 
    