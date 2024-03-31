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

class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.onchange('vehicle_plate_number', 'vehicle_reg_number', 'name')
    def check_duplicate_vehicle_props(self):
        self.ensure_one()
        product = self.env['product.template'].sudo()
        for rec in self:
            if rec.vehicle_plate_number:
                duplicate = product.search([('is_vehicle_product', '=', rec.vehicle_plate_number),('vehicle_plate_number', '=', rec.vehicle_plate_number)], limit=2)
                if len([r for r in duplicate]) > 1:
                    raise ValidationError("Product with same vehicle plate number already existing")
            if rec.vehicle_reg_number:
                duplicate_vp = product.search([('vehicle_reg_number', '=', rec.vehicle_reg_number)], limit=2)
                if len([r for r in duplicate_vp]) > 1:
                    raise ValidationError("Product with same vehicle registration number already existing")
            if rec.name:
                duplicate_name = product.search([('name', '=', rec.name)], limit=2)
                if len([r for r in duplicate_name]) > 1:
                    raise ValidationError("Product with same vehicle name already existing")
    
    is_vehicle_product = fields.Boolean("Is vehicle", default=False)
    vehicle_plate_number = fields.Char("Vehicle Plate Number")
    vehicle_reg_number = fields.Char("Vehicle Reg Number")
    vehicle_color = fields.Char("Vehicle Color")
    vehicle_model = fields.Char("Vehicle Model")
    vehicle_make = fields.Char("Vehicle Make")
    is_available = fields.Char("Is Available")

    @api.onchange('is_vehicle_product')
    def onchange_is_vehicle_product(self):
        if self.is_vehicle_product:
            self.detailed_type = "service"
        
    @api.onchange('vehicle_plate_number')
    def onchange_vehicle_plate_number(self):
        if self.vehicle_plate_number:
            self.default_code = self.vehicle_plate_number
