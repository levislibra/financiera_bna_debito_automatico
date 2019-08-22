# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import math

class FinancieraBnaCobrarWizard(models.TransientModel):
	_name = 'financiera.bna.cobrar.wizard'

	movimiento_id = fields.Many2one('financiera.bna.debito.automatico.movimiento', 'Movimiento')
	payment_date = fields.Date('Fecha de cobro')
	journal_id = fields.Many2one('account.journal', 'Metodo de Cobro', domain="[('type', 'in', ('bank', 'cash'))]")
	payment_amount = fields.Float('Monto a cobrar')
	currency_id = fields.Many2one('res.currency', "Moneda")
	factura_obligatoria = fields.Boolean('Facturacion obligatoria')
	# Facturacion interes
	invoice = fields.Boolean('Facturar cuota')
	invoice_date = fields.Date('Fecha de facturacion', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	factura_electronica = fields.Boolean('Factura electronica?')
	# Facturacion punitorio
	punitorio_invoice = fields.Boolean('Facturar punitorio')
	punitorio_invoice_date = fields.Date('Fecha de facturacion', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	punitorio_factura_electronica = fields.Boolean('Factura electronica')

	@api.model
	def default_get(self, fields):
		rec = super(FinancieraBnaCobrarWizard, self).default_get(fields)
		configuracion_id = self.env.user.company_id.configuracion_id
		rec.update({
			'factura_obligatoria': configuracion_id.factura_obligatoria,
			'invoice': configuracion_id.factura_obligatoria,
			'punitorio_invoice': configuracion_id.factura_obligatoria,
			})
		return rec

	@api.one
	def confirmar_cobrar_movimiento(self):
		self.movimiento_id.confirmar_cobrar_movimiento(self.payment_date, self.journal_id,
			self.invoice, self.invoice_date, self.factura_electronica,
			self.punitorio_invoice, self.punitorio_invoice_date, self.punitorio_factura_electronica)
