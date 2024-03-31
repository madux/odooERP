from odoo import models, fields, api, _
from datetime import datetime, date
from odoo.exceptions import ValidationError
from odoo import http


class PMSJobCategory(models.Model):
    _name = "pms.category"
    _description= "PMS Template category based on job roles"
    _inherit = "mail.thread"

    name = fields.Char(
        string="Name", 
        required=True)
    
    category = fields.Many2one('hr.level.category', string="Category")
    sequence = fields.Char(
        string="Sequence")
        
    kra_weighted_score = fields.Integer(
        string='KRA Section Weight', 
        required=True,
        )
    fc_weighted_score = fields.Integer(
        string='FC Section Weight', 
        required=True,
        )
    lc_weighted_score = fields.Integer(
        string='LC Section Weight', 
        required=True,
        )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('cancel', 'Cancel'),
        ], string="Status", default = "draft", readonly=True)
    
    pms_year_id = fields.Many2one(
        'pms.year', string="Period")
    allow_mid_year_review = fields.Boolean(string="Allow Mid year review",
                                           help="Allow the appraisee to start Mid year review")
    allow_annual_review_submission = fields.Boolean(
        string="Allow Annual review", 
        help="Allow the appraisee to start Annual year review")
    type_of_pms = fields.Selection([
        ('gs', 'Goal Setting'),
        ('hyr', 'Mid year review'),
        ('fyr', 'Annual year review'),
        ], string="Type of PMS", default = "gs", 
        copy=True)
    date_from = fields.Date(
        string="Date From", 
        readonly=False, 
        store=True)
    date_end = fields.Date(
        string="Date End", 
        readonly=False,
        store=True
        )
    deadline = fields.Date(
        string="Deadline Date", 
        store=True)
    
    online_deadline_date = fields.Date(
        string="Online Deadline Date", 
        store=True)

    published_date = fields.Date(
        string="Published date", 
        readonly=True, 
        store=True)
    
    loaded_via_data = fields.Boolean(
        string="Loaded via data", 
        readonly=True, 
        default=False, 
        store=True)

    job_role_ids = fields.Many2many(
        'hr.job', 
        string="Job role"
        )
    section_ids = fields.Many2many(
        'pms.section',
        'pms_section_category_rel',
        'category_id',
        'section_id',
        string="Sections"
    )
    pms_department_ids = fields.Many2many(
        'pms.department', 
        'pms_department_category_rel', 
        'department_id', 
        'category_id',
        string="PMS Department ID")

    active = fields.Boolean(
        string="Active", 
        readonly=True, 
        default=True, 
        store=True)
    
    @api.onchange('category')
    def onchange_category(self):
        if self.category:
            job_role_ids = self.category.job_role_ids
            self.job_role_ids = job_role_ids

    # @api.constrains('category')
    # def check_category(self):
    #     exists = self.env['pms.category'].search([
    #         ('category', '=', self.category.id), 
    #         ('pms_year_id', '=', self.pms_year_id.id)
    #         ])
    #     if len(exists) > 1:
    #         raise ValidationError(f'You have already created a template with level category and same period using {self.category}')

    @api.constrains('job_role_ids')
    def _check_lines(self):
        kra_types = self.mapped('section_ids').filtered(lambda se: se.type_of_section in ['KRA'])
        fc_types = self.mapped('section_ids').filtered(lambda se: se.type_of_section in ['FC'])
        lc_types = self.mapped('section_ids').filtered(lambda se: se.type_of_section in ['LC'])
        if not self.loaded_via_data and not self.mapped('job_role_ids') and not any([kra_types,fc_types,lc_types]):
            raise ValidationError('You must assign at least one job role')
        
    @api.constrains('kra_weighted_score', 'fc_weighted_score', 'lc_weighted_score')
    def check_weights(self):
        weight_total = self.kra_weighted_score + self.fc_weighted_score + self.lc_weighted_score
        if weight_total != 100:
            raise ValidationError("Total of KRA, LC and FC must sum up to 100%")

    @api.onchange('pms_year_id')
    def onchange_year_id(self):
        '''Gets the periodic date interval from the settings'''
        if self.pms_year_id:
            self.date_from = self.pms_year_id.date_from
            self.date_end = self.pms_year_id.date_end
        else:
            self.date_from = False
            self.date_end = False

    def action_notify(self, subject, msg, email_to, email_cc):
        email_from = self.env.user.email
        email_ccs = list(filter(bool, email_cc))
        reciepients = (','.join(items for items in email_ccs)) if email_ccs else False
        mail_data = {
                'email_from': email_from,
                'subject': subject,
                'email_to': email_to,
                'reply_to': email_from,
                'email_cc': reciepients,
                'body_html': msg,
                'state': 'sent'
            }
        mail_id = self.env['mail.mail'].sudo().create(mail_data)
        self.env['mail.mail'].sudo().send(mail_id)
        self.message_post(body=msg)
    
    def get_url(self, id, name):
        base_url = http.request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        base_url += '/web'
        # base_url += '/web#id=%d&view_type=form&model=%s' % (id, name)
        return "<a href={}> </b>Click<a/>. ".format(base_url)

    def send_mail_notification(self, pms_department_obj):
        subject = "Appraisal Notification"
        department_manager = pms_department_obj.department_id.manager_id
        if department_manager:
            email_to = department_manager.work_email
            email_cc = [] #[rec.work_email for rec in self.approver_ids]
            msg = """Dear {}, <br/>
            I wish to notify you that an appraisal template with description, {} \
            has been initialized. You may proceed with publishing it out \
            to staff under your department (Unit).<br/>\
            <br/>Kindly {} to review <br/>\
            Yours Faithfully<br/>{}<br/>HR Department ({})""".format(
                department_manager.name,
                self.name, 
                self.get_url(pms_department_obj.id, pms_department_obj._name),
                self.env.user.name,
                self.env.user.company_id.name,
                )
            self.action_notify(subject, msg, email_to, email_cc)
        else:

            # raise ValidationError(
            #     """
            #     There is no work email address found for the
            #     department manager- {}:""".format(
            #     pms_department_obj.department_id.name)
            # )
            pass
        
    def check_job_role_without_department(self):
        jr = self.mapped('job_role_ids').filtered(
            lambda jr: not jr.department_id)
        if jr:
            raise ValidationError("""
            Please ensure all the selected 
            job roles has departments setup
            """)

    def button_publish(self):
        cancelled_pms_department_ids = self.mapped('pms_department_ids').filtered(
            lambda s: s.state == 'cancel')
        if cancelled_pms_department_ids:
            self.pms_department_ids = [(3, rec.id) for rec in cancelled_pms_department_ids]
        #########
        if self.job_role_ids and self.section_ids:
            self.check_job_role_without_department()
            # filters set of departments to forward generate
            department_ids = set([depart.department_id.id for depart in self.job_role_ids])
            Pms_Department = self.env['pms.department']
            # raise ValidationError(self.section_ids[1].input_weightage)
            if department_ids:
                # create pms.department record
                for dep in department_ids:
                    department_id = self.env['hr.department'].browse([dep])
                    pms_department = Pms_Department.create({
                        'name': self.name,
                        'department_id': department_id.id,
                        'department_manager_id': department_id.manager_id.id,
                        'pms_year_id': self.pms_year_id.id,
                        'type_of_pms': self.type_of_pms,
                        'date_from': self.pms_year_id.date_from,
                        'date_end': self.pms_year_id.date_end,
                        'deadline': self.deadline,
                        'state': 'review',
                        'hr_category_id': self.id,
                        'section_line_ids': [(0, 0, {
                            # 'pms_department_id': dep.id,
                            # creating pms.department.section
                            'section_id': sec.id,
                            'dep_input_weightage': sec.input_weightage,
                            'name': sec.name,
                            'max_line_number': sec.max_line_number,
                            'min_line_number': sec.min_line_number,
                            'type_of_section': sec.type_of_section,
                            'pms_category_id': self.id,
                            # 'weighted_score': sec.weighted_score,
                            'section_avg_scale': sec.section_avg_scale,
                            # creating pms.department.section.line
                            'section_line_ids': [(0, 0, {
                                'name': sec_line.name,
                                'section_line_id': sec_line.id,
                                'section_id': sec.id,
                                'is_required': sec_line.is_required,
                                'description': sec_line.description,
                                'kba_description_ids': [(0, 0, {
                                    'name': kba.name,
                                }) for kba in sec_line.kba_description_ids],
                            }) for sec_line in sec.section_line_ids]
                        }) for sec in self.section_ids],
                        
                    })
                    # for sec in self.section_ids:
                    #     vals = {
                    #         'pms_department_id': pms_department.id,
                    #         'section_id': sec.id,
                    #         'input_weightage': sec.input_weightage,
                    #         'name': sec.name + 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                    #         'max_line_number': sec.max_line_number,
                    #         'type_of_section': sec.type_of_section,
                    #         'pms_category_id': self.id,
                    #         # 'weighted_score': sec.weighted_score,
                    #         'section_avg_scale': sec.section_avg_scale,
                    #     }
                    #     pms_dep_section_id = self.env['pms.department.section'].create(vals)
                    #     for sec_line in sec.mapped('section_line_ids'):
                    #         vals = {
                    #             'pms_department_section_id': pms_dep_section_id.id,
                    #             'name': sec_line.name + 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                    #             'section_id': sec.id,
                    #             'is_required': sec_line.is_required,
                    #             'description': sec_line.description,
                    #         }
                    #         self.env['pms.department.section.line'].create(vals)

                    # after generating the record, send notification email
                    self.write({
                        'pms_department_ids': [(4, pms_department.id)], 
                        })
                    self.send_mail_notification(pms_department)
            self.write({
                'state':'published',
                'published_date': fields.Date.today(),
            })
        else:
            raise ValidationError('Please add sections and job roles')
    
    def _message_post(self, template):
        """Wrapper method for message_post_with_template
        Args:
            template (str): email template
        """
        if template:
            ir_model_data = self.env['ir.model.data']
            # template_id = ir_model_data.get_object_reference('hr_pms', template)[1]
            template_id = self.env.ref(f'hr_pms.{template}')
            self.message_post_with_template(
                template_id, composition_mode='comment',
                model='{}'.format(self._name), res_id=self.id,
                email_layout_xmlid='mail.mail_notification_light',
            )
     
    def button_cancel(self):
        for rec in self.mapped('pms_department_ids'): #.filtered(
            # lambda s: s.state in ['draft', 'review']):
            rec.write({'active': False, 'state': 'cancel'})
        self.write({
                'state':'cancel'
            })
    
    def button_republish(self):
        for rec in self.env['pms.department'].search([('active', '=', False), ('hr_category_id', '=', self.id)]):
            rec.write({'active': True, 'state': 'review'})
        self.write({
                'state':'published'
            })
        
    def button_set_to_draft(self):
        self.write({
                'state':'draft'
            })