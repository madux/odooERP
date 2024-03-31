from datetime import datetime, timedelta
import time
import base64
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo import http
import logging
from lxml import etree
import random

_logger = logging.getLogger(__name__)

class HRLevelcategory(models.Model):
    _name = "hr.level.category"
    _rec_name = "category"
    _description = "HR level category"

    category = fields.Selection([
        ('Junior Management', 'Junior Management'),
        ('Middle Management', 'Middle Management'),
        ('Senior Management', 'Senior Management'),
        ], string="Category", default = "", required=True)
    
    job_role_ids = fields.Many2many(
        'hr.job',
        'hr_job_level_rel',
        'hr_level_id',
        'hr_job_id',
        string="Job roles",
        required=True
    )

    def action_set_job_role(self):
        'this is just for the migration of existing records'
        if self.category:
            Employee = self.env['hr.employee']
            domain = []
            if self.category == "Junior Management":
                domain = [('level_id.name', 'in', ['JM', 'Junior Management', 'Junior Mgt', 'Junior'])]
            elif self.category == "Middle Management":
                domain = [('level_id.name', 'in', ['MM', 'Middle Management', 'Middle Mgt', 'Middle'])]
            elif self.category == "Senior Management":
                domain = [('level_id.name', 'in', ['SM', 'Senior Management', 'Senior Mgt', 'Senior'])]
            employees = Employee.search(domain)
            self.job_role_ids = False 
            if employees:
                for rec in employees:
                    self.job_role_ids = [(4, rec.job_id.id)]

    @api.constrains('category')
    def check_category(self):
        exists = self.env['hr.level.category'].search([('category', '=', self.category)])
        if len(exists) > 1:
            raise ValidationError(f'You have already create level category using {self.category}')

class HRUnit(models.Model):
    _name = "hr.region"
    _description = "HR Region"

    name = fields.Char(
        string="Name", 
        required=True
        )

class HRUnit(models.Model):
    _name = "hr.work.unit"
    _description = "HR work unit"

    name = fields.Char(
        string="Name", 
        required=True
        )


class HRDistrict(models.Model):
    _name = "hr.district"
    _description = "HR district"

    name = fields.Char(
        string="Name", 
        required=True
        )

class HRLevel(models.Model):
    _name = "hr.level"
    _description = "HR level"

    name = fields.Char(
        string="Name", 
        required=True
        )
    
class HRUNIT(models.Model):
    _name = "hr.unit"
    _description = "HR Unit"

    name = fields.Char(
        string="Name", 
        required=True
        )
    
class HRgrade(models.Model):
    _name = "hr.grade"
    _description = "HR grade"

    name = fields.Char(
        string="Name", 
        required=True
        )

# class HrEmployeePublicInherit(models.Model):
#     _inherit = "hr.employee.public"
    
#     administrative_supervisor_id = fields.Many2one('hr.employee', string="Administrative Supervisor")
#     reviewer_id = fields.Many2one('hr.employee', string="Reviewer")
#     employment_date = fields.Date(string="Employement date")
#     level_id = fields.Many2one('hr.level', string="Level")
#     grade_id = fields.Many2one('hr.grade', string="Grade")
#     work_unit_id = fields.Many2one('hr.work.unit', string="Unit/SC/Workshop/Substation")
#     unit_id = fields.Many2one('hr.unit', string="Unit")
#     ps_district_id = fields.Many2one('hr.district', string="Employee District")
#     employee_number = fields.Char(
#         string="Staff Number", 
#         )
#     migrated_password = fields.Char(
#         string="migrated password", 
#         ) 
#     pms_number_appraisal = fields.Integer(string="Appraisal",)# compute="_compute_employees_component")
#     pms_number_queries = fields.Integer(string="Queries",)# compute="_compute_employees_component")
#     pms_number_commendation = fields.Integer(string="Commendation",)# compute="_compute_employees_component")
#     pms_number_warning = fields.Integer(string="Queries", )#compute="_compute_employees_component")
#     pms_number_absent = fields.Integer(string="Absent", )#compute="_compute_employees_component")

class HrEmployee(models.Model):
    _inherit = "hr.employee" 

    def make_name_capitalize(self):
        rec_ids = self.env.context.get('active_ids', [])
        for rec in rec_ids:
            record = self.env['hr.employee'].browse([rec])
            if record.name:
                record.update({'name': record.name.upper()})

    def update_pms_user_group(self, user, groups=[]):
        emp_group = self.env.ref("hr_pms.group_pms_user_id")
        # reviewer_group = self.env.ref("hr_pms.group_pms_reviewer")
        groups.append(emp_group.id)
        group_list = [(6, 0, groups)]
        if user:
            user.sudo().write({'groups_id':group_list})

    def auto_update_employee_appraisers_role(self):
        rec_ids = self.env.context.get('active_ids', [])
        records = self.env['hr.employee'].browse(rec_ids)
        for rec in records:
            if rec.administrative_supervisor_id:
                rec.update_administrative_supervisor_user(rec.administrative_supervisor_id.user_id)
            if rec.parent_id:
                rec.update_parent_id_user(rec.parent_id.user_id)
            if rec.reviewer_id:
                rec.update_reviewer_id_user(rec.reviewer_id.user_id)

    # @api.onchange('administrative_supervisor_id')
    def update_administrative_supervisor_user(self, userId):
            supervisor_group = self.env.ref("hr_pms.group_pms_supervisor")
            groups = [supervisor_group.id]
            self.update_pms_user_group(userId, groups)

    # @api.onchange('parent_id')
    def update_parent_id_user(self, userId):
        '''Updating manager / function appraiser user role'''
        supervisor_group = self.env.ref("hr_pms.group_pms_supervisor")
        groups = [supervisor_group.id]
        self.update_pms_user_group(userId, groups)
    
    # @api.onchange('reviewer_id')
    def update_reviewer_id_user(self, userId):
        reviewer_group = self.env.ref("hr_pms.group_pms_reviewer")
        groups = [reviewer_group.id]
        self.update_pms_user_group(userId, groups)

class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    @api.constrains('employee_number')
    def _check_duplicate_employee_number(self):
        employee = self.env['hr.employee'].sudo()
        if self.employee_number not in ["", False]:
            duplicate_employee = employee.search([('employee_number', '=', self.employee_number)], limit=2)
            if len([r for r in duplicate_employee]) > 1:
                raise ValidationError("Employee with same staff ID already existing")

    # pms_appraisal_ids = fields.Many2many('usl.employee.appraisal', string="Appraisals", readonly=True)
    administrative_supervisor_id = fields.Many2one('hr.employee', string="Administrative Supervisor")
    reviewer_id = fields.Many2one('hr.employee', string="Reviewer")
    hr_region_id = fields.Many2one('hr.region', string="Region")
    employment_date = fields.Date(string="Employement date")
    level_id = fields.Many2one('hr.level', string="Level")
    grade_id = fields.Many2one('hr.grade', string="Grade")
    work_unit_id = fields.Many2one('hr.work.unit', string="Unit/SC/Workshop/Substation")
    unit_id = fields.Many2one('hr.unit', string="Unit")
    ps_district_id = fields.Many2one('hr.district', string="Employee District")
    employee_number = fields.Char(
        string="Staff Number", 
        )
    migrated_password = fields.Char(
        string="migrated password", 
        )
    login_username = fields.Char(
        string="Login", 
        related="user_id.login"
        )
    pms_number_appraisal = fields.Integer(string="Appraisal",)# compute="_compute_employees_component")
    pms_number_queries = fields.Integer(string="Queries",)# compute="_compute_employees_component")
    pms_number_commendation = fields.Integer(string="Commendation",)# compute="_compute_employees_component")
    pms_number_warning = fields.Integer(string="Queries", )#compute="_compute_employees_component")
    pms_number_absent = fields.Integer(string="Absent", )#compute="_compute_employees_component")

    def reset_employee_user_password(self):
        for rec in self:
            if rec.user_id:
                change_password_wiz = self.env['change.password.wizard'].sudo()
                change_password_user = self.env['change.password.user'].sudo()
                new_password = password = ''.join(random.choice('EdcpasHwodfo!xyzus$rs1234567') for _ in range(10))
                change_password_wiz_id = change_password_wiz.create({
                    'user_ids': [(0, 0, {
                        'user_login': rec.user_id.login, 
                        'new_passwd': new_password,
                        'user_id': rec.user_id.id,
                        })]
                })
                change_password_wiz_id.user_ids[0].change_password_button()
                rec.migrated_password = new_password
                # self.send_credential_notification()
            else:
                raise ValidationError('Employee is not related to any user. Kindly contact system admin to create a user for the employee')
    
    def reset_multiple_employee_user_password(self):
        rec_ids = self.env.context.get('active_ids', [])
        for record in rec_ids:
            rec = self.env['hr.employee'].browse([record])
            if rec.user_id:
                change_password_wiz = self.env['change.password.wizard'].sudo()
                change_password_user = self.env['change.password.user'].sudo()
                new_password = password = ''.join(random.choice('EdcpasHwodfo!xyzus$rs1234567') for _ in range(10))
                change_password_wiz_id = change_password_wiz.create({
                    'user_ids': [(0, 0, {
                        'user_login': rec.user_id.login, 
                        'new_passwd': new_password,
                        'user_id': rec.user_id.id,
                        })]
                })
                change_password_wiz_id.user_ids[0].change_password_button()
                rec.update({'migrated_password': new_password})

    # def _message_post(self, template):
    #     """Wrapper method for message_post_with_template

    #     Args:
    #         template (str): email template
    #     """
    #     if template:
    #         self.message_post_with_template(
    #             template.id, composition_mode='comment',
    #             model='hr.employee', res_id=self.id,
    #             email_layout_xmlid='mail.mail_notification_light',
    #         )
    

    def send_credential_notification(self):
        MAIL_TEMPLATE = self.env.ref(
        'hr_pms.mail_template_pms_notification', raise_if_not_found=False)
        # self.with_context(allow_write=True)._message_post(
        #     MAIL_TEMPLATE)  mail_template_non_email_subordinates_pms_notification
        rec_ids = self.env.context.get('active_ids', [])
        template_to_use = "mail_template_pms_notification"
        for rec in rec_ids:
            record = self.env['hr.employee'].browse([rec])
            if record.work_email or record.private_email:
                email_to = record.work_email or record.private_email 
                template_to_use = "mail_template_pms_notification"
            else: # either send it to the employee manager or supervisors email
                email_to = record.parent_id.work_email or record.administrative_supervisor_id.work_email 
                template_to_use = "mail_template_non_email_subordinates_pms_notification"
            # ir_model_data = self.env['ir.model.data']
            # template_id = ir_model_data.get_object_reference('hr_pms', template_to_use)[1] 
            template = self.env.ref(f'hr_pms.{template_to_use}')
            if template:
                ctx = dict()
                ctx.update({
                    'default_model': 'hr.employee',
                    'default_res_id': record.id,
                    'default_use_template': bool(template),
                    'default_template_id': template.id,
                    'default_composition_mode': 'comment',
                })
                # template_rec = self.env['mail.template'].browse([template_id.id])
                if email_to:
                    template.write({'email_to': email_to})
                template.with_context(ctx).send_mail(record.id, False)
            # record.action_send_mail(
            #     'mail_template_pms_notification', 
            #     [record.work_email, record.private_email],
            #     )

    def generate_user_record(self):
        emp_portal_group = self.env.ref("base.group_portal")
        emp_internal_group = self.env.ref("base.group_user")
        emp_memo_user_group = self.env.ref("company_memo.mainmemo_officer")
        Group = self.env['res.groups'].sudo()
        group_list = [(4, emp_portal_group.id)]
        rec_ids = self.env.context.get('active_ids', [])
        for rec in rec_ids:
            record = self.env['hr.employee'].browse([rec])
            email = record.work_email or record.private_email
            fullname = record.name
            user, password = False, False
            login = email if email and email.endswith('@enugudisco.com') else record.employee_number
            if login:
                password = ''.join(random.choice('EdcpasHwodfo!xyzus$rs1234567') for _ in range(10))
                user_vals = {
                'name' : fullname,
                'login' : login,
                'password': password,
                }
                _logger.info(f"Creating employee Rep User..with password --- and login {login}.")
                User = self.env['res.users'].sudo()
                user = User.search([('login', '=', login)],limit=1)

                groups_to_remove = Group.search(
                    ['|',
                    ('name', '=', 'Contact Creation'),
                    ('id', 'in', [
                    self.env.ref('base.group_user').id,
                    self.env.ref('base.group_public').id,
                    ]),
                    ])
                for group in groups_to_remove:
                    tup = (3,group.id)
                    group_list.append(tup)
                    
                if user:
                    _logger.info("User already exists...")
                    password = False
                else:
                    user = User.create(user_vals)
                    _logger.info("Creating User record...")
                _logger.info('Adding user to group ...')

                # employee_exists_as_manager = self.env['hr.department'].search([('manager_id', '=', record.id)], limit=1)
                # if employee_exists_as_manager:
                #     tup = (3,emp_portal_group.id)
                #     group_list.append(tup)
                #     # group_list = [
                #     #     (4, emp_internal_group.id), 
                #     #     (4, emp_memo_user_group.id), 
                #     #     ]
                # else:
                #     # group_list = [(3, emp_internal_group.id)]
                #     tup = (3,emp_internal_group.id)
                #     group_list.append(tup)
                user.sudo().write({'groups_id':group_list})
                record.sudo().write({'user_id': user.id, 'migrated_password': password})
    
    # def action_send_mail(self, with_template_id, email_items= None, email_from=None):
    #     '''Email_to = [lists of emails], Contexts = {Dictionary} '''
    #     email_to = (','.join([m for m in email_items])) if email_items else False
    #     ir_model_data = self.env['ir.model.data']
    #     template_id = ir_model_data.get_object_reference('hr_pms', 'mail_template_pms_notification')[1]         
    #     if template_id:
    #         ctx = dict()
    #         ctx.update({
    #             'default_model': 'hr.employee',
    #             'default_res_id': self.id,
    #             'default_use_template': bool(template_id),
    #             'default_template_id': template_id,
    #             'default_composition_mode': 'comment',
    #         })
    #         template_rec = self.env['mail.template'].browse(template_id)
    #         if email_to:
    #             template_rec.write({'email_to': email_to})
    #         template_rec.with_context(ctx).send_mail(self.id, True)

    # @api.depends('appraisal_ids')
    # def _compute_employees_component(self):
    #     for rec in self:
    #         appraisals = self.env['usl.employee.appraisal'].search([('employee_id', '=', rec.id)])
    #         appr = rec.appraisal_ids
    #         rec.number_appraisal = len(rec.appraisal_ids)
    #         rec.number_queries = sum([amt.number_queries for amt in rec.appraisal_ids])
    #         rec.number_warning = sum([amt.number_warning for amt in rec.appraisal_ids])
    #         rec.number_commendation = sum([amt.number_commendation for amt in rec.appraisal_ids])
    #         rec.number_absent = sum([amt.number_absent for amt in rec.appraisal_ids])

    def open_employee_appraisals(self):
        pass 
        # for rec in self:
        #     appraisals = self.env['usl.employee.appraisal'].search([('employee_id', '=', self.id)])
        #     emp_appraisal = [rec.id for rec in appraisals] if appraisals else []
        #     form_view_ref = self.env.ref('maach_hr_appraisal.usl_employee_appraisal_form_view', False)
        #     tree_view_ref = self.env.ref('maach_hr_appraisal.view_usl_employee_appraisal_tree', False)
        #     return {
        #         'domain': [('id', 'in', emp_appraisal)],
        #         'name': 'Employee Appraisal',
        #         'res_model': 'usl.employee.appraisal',
        #         'type': 'ir.actions.act_window',
        #         'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
        #         'target': 'current',
        #     }

    def stat_button_query(self):
        pass

    def stat_button_number_commendation(self):
        pass

    def stat_button_warning(self):
        pass

    def stat_button_absent(self):
        pass

    def stat_button_total_appraisal(self):
        pass

# class HrEmployeePrivate(models.Model):
#     _inherit = "hr.employee"

    # def update_pms_user_group(self, user, groups=[]):
    #     emp_group = self.env.ref("hr_pms.group_pms_user_id")
    #     # reviewer_group = self.env.ref("hr_pms.group_pms_reviewer")
    #     groups.append(emp_group.id)
    #     group_list = [(6, 0, groups)]
    #     if user:
    #         user.sudo().write({'groups_id':group_list})

    # @api.onchange('administrative_supervisor_id')
    # def update_administrative_supervisor_user(self): 
    #     if self.administrative_supervisor_id:
    #         if self.administrative_supervisor_id.user_id:
    #             supervisor_group = self.env.ref("hr_pms.group_pms_supervisor")
    #             groups = [supervisor_group.id]
    #             self.update_pms_user_group(self.administrative_supervisor_id.user_id, groups)

    # @api.onchange('parent_id')
    # def update_parent_id_user(self):
    #     user = self.parent_id
    #     if user and user.user_id:
    #         supervisor_group = self.env.ref("hr_pms.group_pms_supervisor")
    #         groups = [supervisor_group.id]
    #         self.update_pms_user_group(user.user_id, groups)
    #     else:
    #         pass 
    
    # @api.onchange('reviewer_id')
    # def update_reviewer_id_user(self):
    #     if self.reviewer_id:
    #         reviewer_group = self.env.ref("hr_pms.group_pms_reviewer")
    #         group = self.env['res.groups'].sudo().browse([reviewer_group.id])
    #         group.update({
    #             'users': [(4, self.reviewer_id.user_id.id)]
    #         })
            # .users = [(6, 0, [self.reviewer_id.user_id.id])]
            # groups = [reviewer_group.id]
            # group_list = [(6, 0, groups)]
            # if user.user_id:
            #     user.user_id.sudo().update({'groups_id':group_list})
            # raise ValidationError(self.reviewer_id.name)
            # self.update_pms_user_group(user.user_id, groups)