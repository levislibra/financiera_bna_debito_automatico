# -*- coding: utf-8 -*-

from openerp import models, fields, api


class ExtendsResCompany(models.Model):
	_name = 'res.company'
	_inherit = 'res.company'

	barrido_cbu_bna = fields.Boolean('Barrido por CBU Banco Nacion mediante archivo')
