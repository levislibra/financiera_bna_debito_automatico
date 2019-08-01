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

	name = fields.Char('Nombre', compute='_compute_name')
	configuracion_id = fields.Many2one('financiera.bna.debito.automatico.configuracion', 'Cuenta de Recaudacion')
	state = fields.Selection(
		[('borrador', 'Borrador'), ('generado', 'Generado'), ('finalizado', 'Finalizado')],
		string='Estado', default='borrador')
	moneda_movimiento = fields.Selection(
		[('P', 'Pesos'), ('D', 'Dolares')],
		string='Moneda del movimiento', default='P')
	fecha_tope_rendicion = fields.Date('Fecha tope de rendicion')
	empleados_bna = fields.Selection(
		[('BNA', 'Todos los clientes del lote son empleados del BNA'),
		('EMP', 'Si los clientes del lote no son empleados BNA pero perciben haberes a través de éste'),
		('REE', 'Cuando al menos 1 (un) cliente del lote no percibe haberes a través del BNA es decir es cliente común')],
		string='Empledos BNA', default='REE')
	mes_tope_rendicion = fields.Char('Mes fecha tope de rendicion', help='Con formato MM', size=2)
	nro_archivo_enviado_mes = fields.Char('Nro de archivo que se envia en el mes', help='Comenzando desde 01', size=2)
	archivo_generado = fields.Binary('Archivo generado')
	archivo_resultado = fields.Binary('Archivo resultado')

	cuota_ids = fields.One2many('financiera.prestamo.cuota', 'bna_movimiento_id', 'Cuotas')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.movimiento'))


	@api.one
	def _compute_name(self):
		self.name = 'Mes '+self.mes_tope_rendicion+' - Archivo '+self.nro_archivo_enviado_mes

	@api.one
	def generar_archivo(self):
		self.write({
			'state': 'generado',
		})

	@api.one
	def enviar_a_borrador(self):
		self.write({
			'state': 'borrador',
		})

	@api.one
	def aplicar_archivo(self):
		self.write({
			'state': 'finalizado',
		})

	# def mes_to_maskmes(self, mes):
	# 	ret = None
	# 	if mes >= 1 and mes <= 9:
	# 		ret = "0" + str(mes)
	# 	elif mes >= 10 and mes <= 12:
	# 		ret = str(mes)
	# 	return ret

	@api.onchange('fecha_tope_rendicion')
	def _onchange_fecha_tope_rendicion(self):
		if self.fecha_tope_rendicion != False:
			formato_fecha = "%Y-%m-%d"
			fecha_tope_rendicion = datetime.strptime(self.fecha_tope_rendicion, formato_fecha)
			string_fecha_inicio_mes = str(fecha_tope_rendicion.year)+"-"+str(fecha_tope_rendicion.month).zfill(2)+"-01"
			string_mes_siguiente = None
			string_anio = str(fecha_tope_rendicion.year)
			if fecha_tope_rendicion.month == 12:
				string_mes_siguiente = "01"
				string_anio = str(fecha_tope_rendicion.year+1)
			else:
				string_mes_siguiente = str(fecha_tope_rendicion.month+1).zfill(2)
			string_fecha_inicio_mes_siguiente = string_anio+"-"+string_mes_siguiente+"-01"
			cr = self.env.cr
			uid = self.env.uid
			movimiento_obj = self.pool.get('financiera.bna.debito.automatico.movimiento')
			movimiento_ids = movimiento_obj.search(cr, uid, [
				('state', '=', 'generado'),
				('fecha_tope_rendicion', '>=', string_fecha_inicio_mes),
				('fecha_tope_rendicion', '<', string_fecha_inicio_mes_siguiente),
				('company_id', '=', self.company_id.id)])
			self.mes_tope_rendicion = str(fecha_tope_rendicion.month).zfill(2)
			self.nro_archivo_enviado_mes = str(len(movimiento_ids)+1).zfill(2)

class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	bna_movimiento_id = fields.Many2one('financiera.bna.debito.automatico.movimiento', 'Movimiento BNA debito automatico')