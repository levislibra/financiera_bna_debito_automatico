# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
import time

class FinancieraBnaDebitoAutomaticoConfiguracion(models.Model):
	_name = 'financiera.bna.debito.automatico.configuracion'

	name = fields.Char('Nombre', compute='_compute_name')
	sucursal_bna_recaudacion = fields.Char("Sucursal de la cuenta de recaudacion (4 digitos)", size=4)
	tipo_moneda_cuenta = fields.Selection(
		[(10, 'Cuenta Corriente $'), (11, 'Cuenta Corriente u$s'),
		(20, 'Caja de Ahorro $'), (21, 'Caja de Ahorro u$s'),
		(27, 'Cta.Cte. Especial $'), (28, 'Cta.Cte. Especial u$s')],
		string='Tipo y moneda de la cuenta')
	cuenta_bna_recaudacion = fields.Char("Cuenta de recaudacion (10 digitos)", size=10)
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.configuracion'))

	@api.one
	def _compute_name(self):
		self.name = 'Suc. '+self.sucursal_bna_recaudacion+' - Tipo '+str(self.tipo_moneda_cuenta)+' - Cuenta '+self.cuenta_bna_recaudacion

class FinancieraBnaDebitoAutomaticoMovimiento(models.Model):
	_name = 'financiera.bna.debito.automatico.movimiento'

	configuracion_id = fields.Many2one('financiera.bna.debito.automatico.configuracion', 'Cuenta de Recaudacion')
	state = fields.Selection(
		[('borrador', 'Borrador'), ('generado', 'Generado'), ('finalizado', 'Finalizado')],
		string='Estado', default='borrador')
	moneda_movimiento = fields.Selection(
		[('P', 'Pesos'), ('D', 'Dolares')],
		string='Moneda del movimiento', default='P')
	fecha_tope_rendicion = fields.Date('Fecha tope de rendicion', default=lambda *a: time.strftime('%Y-%m-%d'))
	empleados_bna = fields.Selection(
		[('BNA', 'Todos los clientes del lote son empleados del BNA'),
		('EMP', 'Si los clientes del lote no son empleados BNA pero perciben haberes a través de éste'),
		('REE', 'Cuando al menos 1 (un) cliente del lote no percibe haberes a través del BNA es decir es cliente común')],
		string='Empledos BNA', default='REE')

	cuota_ids = fields.One2many('financiera.prestamo.cuota', 'bna_movimiento_id', 'Cuotas')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.movimiento'))


class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	bna_movimiento_id = fields.Many2one('financiera.bna.debito.automatico.movimiento', 'Movimiento BNA debito automatico')