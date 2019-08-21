# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from openerp.exceptions import UserError, ValidationError
import time
import base64
from tempfile import TemporaryFile

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
		[('borrador', 'Borrador'), ('generado', 'Generado'), ('cancelado', 'Cancelado'), ('finalizado', 'Finalizado')],
		string='Estado', default='borrador')
	moneda_movimiento = fields.Selection(
		[('P', 'Pesos'), ('D', 'Dolares')],
		string='Moneda del movimiento', default='P')
	fecha_tope_rendicion = fields.Date('Fecha tope de rendicion')
	empleados_bna = fields.Selection(
		[('BNA', 'BNA - Todos los clientes del lote son empleados del BNA'),
		('EMP', 'EMP - Si los clientes del lote no son empleados BNA pero perciben haberes a través de éste'),
		('REE', 'REE - Cuando al menos 1 (un) cliente del lote no percibe haberes a través del BNA es decir es cliente común')],
		string='Empledos BNA', default='REE')
	mes_tope_rendicion = fields.Char('Mes fecha tope de rendicion', help='Con formato MM', size=2)
	nro_archivo_enviado_mes = fields.Char('Nro de archivo que se envia en el mes', help='Comenzando desde 01', size=2)
	archivo_generado = fields.Binary('Archivo generado')
	archivo_resultado = fields.Binary('Archivo resultado')
	cuota_fecha_hasta = fields.Date("Fecha hasta")
	cuota_ids = fields.Many2many('financiera.prestamo.cuota', 'financiera_bna_movimiento_cuota_rel', 'bna_movimiento_id', 'cuota_id', 'Cuotas')
	movimiento_linea_ids = fields.One2many('financiera.bna.debito.automatico.movimiento.linea','movimiento_id', 'Resultados')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.movimiento'))


	@api.one
	def _compute_name(self):
		self.name = 'Mes '+self.mes_tope_rendicion+' - Archivo '+self.nro_archivo_enviado_mes

	@api.one
	def asignar_cuotas(self):
		cr = self.env.cr
		uid = self.env.uid
		cuota_obj = self.pool.get('financiera.prestamo.cuota')
		cuota_ids = cuota_obj.search(cr, uid, [
			('state', '=', 'activa'),
			('debito_automatico_cuota', '=', True),
			('bna_debito_disponible', '=', True),
			('fecha_vencimiento', '<=', self.cuota_fecha_hasta),
			('company_id', '=', self.company_id.id)])
		self.cuota_ids = [(6, 0, cuota_ids)]

	@api.one
	def generar_archivo(self):
		file = TemporaryFile('w+')
		fecha_tope_rendicion = datetime.strptime(self.fecha_tope_rendicion, "%Y-%m-%d")
		# Escribimos el encabezado
		encabezado = "1"
		encabezado += self.configuracion_id.sucursal_bna_recaudacion
		encabezado += str(self.configuracion_id.tipo_moneda_cuenta)
		encabezado += self.configuracion_id.cuenta_bna_recaudacion
		encabezado += str(self.moneda_movimiento)
		encabezado += "E"
		encabezado += self.mes_tope_rendicion
		encabezado += self.nro_archivo_enviado_mes
		encabezado += str(fecha_tope_rendicion.year)
		encabezado += str(fecha_tope_rendicion.month).zfill(2)
		encabezado += str(fecha_tope_rendicion.day).zfill(2)
		encabezado += str(self.empleados_bna)
		encabezado += "".ljust(94)
		encabezado += "\n"
		# Escribimos los registro tipo 2
		registros = ""
		total_a_debitar = 0
		for cuota_id in self.cuota_ids:
			if cuota_id.bna_debito_disponible:
				cuota_id.bna_debito_disponible = False
				registros += "2" 
				if cuota_id.debito_automatico_cuota_cbu.sucursal != False and len(cuota_id.debito_automatico_cuota_cbu.sucursal) == 4:
					registros += cuota_id.debito_automatico_cuota_cbu.sucursal
				else:
					raise ValidationError("Cuota "+str(cuota_id.name)+". La sucursal del banco no cumple los requerimientos.")
				# Hardcore CA - Supuestamente siempre sera CA: Caja de Ahorro
				registros += "CA"
				# Cuenta a debitar primera posicion 0 y N(10) para Nro de cuenta del cliente
				registros += "0"
				if cuota_id.debito_automatico_cuota_cbu.acc_number != False and len(cuota_id.debito_automatico_cuota_cbu.acc_number) == 10:
					registros += cuota_id.debito_automatico_cuota_cbu.acc_number
				else:
					raise ValidationError("El Nro de cuenta de la cuota "+str(cuota_id.name)+" no cumple los requerimientos.")
				# Importe a debitar N(15) 13,2
				if cuota_id.saldo > 0:
					registros += str(cuota_id.saldo).replace('.', '').zfill(15)
					total_a_debitar += cuota_id.saldo
				else:
					raise ValidationError("El Importe de la cuota "+str(cuota_id.name)+" no cumple los requerimientos.")
				# Empresa envia 0 N(8) - BNA devuelve fecha de cobro
				registros += "00000000"
				# Empresa envia 0 N(1) - BNA devuelve 0 si aplicado
				# 9 si fue rechazado
				registros += "0"
				# Empresa envia blancos N(30)
				registros += "                              "
				# Empresa campo N(10) de uso interno
				ml_values = {
					'cuota_id': cuota_id.id,
					'monto_a_debitar': cuota_id.saldo,
				}
				new_movimiento_linea_id = self.env['financiera.bna.debito.automatico.movimiento.linea'].create(ml_values)
				self.movimiento_linea_ids = [new_movimiento_linea_id.id]
				registros += str(new_movimiento_linea_id.id).zfill(10)
				registros += "".ljust(46)
				registros += "\n"
			else:
				raise ValidationError("La cuota: "+str(cuota_id.name) + " no esta disponible para debito por cbu.")
		# Un Registro tipo 3
		finalizar = "3"
		# Importe total a debitar N(15) 13,2
		finalizar += str(total_a_debitar).replace('.', '').zfill(15)
		# Cantidad de registros tipo 2 que se envian N(6)
		finalizar += str(len(self.cuota_ids)).zfill(6)
		# Empresa envia 0 N(15) - BNA devuelve monto no aplicado
		finalizar += "0".zfill(15)
		# Empresa envia 0 N(6) - BNA cant de reg. no aplicados
		finalizar += "0".zfill(6)
		# Agregamos blancos para cumplicar con los 128 bit a enviar
		finalizar += "".ljust(85)
		finalizar += "\n"
		
		file_read = base64.b64encode(encabezado+registros+finalizar)
		self.archivo_generado = file_read

		self.write({
			'state': 'generado',
		})

	@api.one
	def enviar_a_cancelado(self):
		for cuota_id in self.cuota_ids:
			cuota_id.bna_debito_disponible = True
		for movimiento_line_id in self.movimiento_linea_ids:
			movimiento_line_id.state = 'cancelado'
		self.write({
			'state': 'cancelado',
		})

	@api.one
	def enviar_a_generado(self):
		for cuota_id in self.cuota_ids:
			if cuota_id.bna_debito_disponible:
				cuota_id.bna_debito_disponible = False
			else:
				raise ValidationError("La cuota: "+str(cuota_id.name) + "ya no esta disponible para debito por cbu.")
		self.write({
			'state': 'generado',
		})

	@api.one
	def aplicar_archivo(self):
		self.write({
			'state': 'finalizado',
		})

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

class FinancieraBnaDebitoAutomaticoMovimientoCuota(models.Model):
	_name = 'financiera.bna.debito.automatico.movimiento.linea'

	_rec = 'cuota_id'
	movimiento_id = fields.Many2one('financiera.bna.debito.automatico.movimiento', 'Movimiento de debito automatico')
	cuota_id = fields.Many2one('financiera.prestamo.cuota', 'Cuota')
	monto_a_debitar = fields.Float('Monto a debitar', digits=(16,2))
	monto_debitado = fields.Float('Monto debitado', digits=(16,2))
	monto_no_debitado = fields.Float('Monto no debitado', digits=(16,2))
	descripcion = fields.Char('Descripcion del rechazo', size=30)
	fecha_del_debito = fields.Date('Fecha del debito')
	state = fields.Selection(
		[('borrador', 'Borrador'),
		(0, 'Cobrado'),
		(9, 'Rechazado'),
		('cancelado', 'Cancelado')],
		string='Estado', default='borrador')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.movimiento.linea'))


class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	bna_movimiento_ids = fields.Many2many('financiera.bna.debito.automatico.movimiento', 'financiera_bna_movimiento_cuota_rel', 'cuota_id', 'bna_movimiento_id', 'BNA debitos')
	bna_debito_automatico_linea_ids = fields.One2many('financiera.bna.debito.automatico.movimiento.linea', 'cuota_id', 'BNA resultados de debitos')
	bna_debito_disponible = fields.Boolean('Disponible para debito BNA?', default=True)


