# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from openerp.exceptions import UserError, ValidationError
import time
import base64

class FinancieraBnaDebitoAutomaticoConfiguracion(models.Model):
	_name = 'financiera.bna.debito.automatico.configuracion'

	name = fields.Char('Nombre', compute='_compute_name')
	sucursal_bna_recaudacion = fields.Char("Sucursal de la cuenta de recaudacion (4 digitos)", size=4)
	active = fields.Boolean("Activa", default=True)
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

	_order = 'id desc'
	name = fields.Char('Nombre', compute='_compute_name')
	configuracion_id = fields.Many2one('financiera.bna.debito.automatico.configuracion', 'Cuenta de Recaudacion')
	state = fields.Selection(
		[('borrador', 'Borrador'),
		('generado', 'Generado'),
		('aplicado', 'Aplicado'),
		('finalizado', 'Finalizado'),
		('cancelado', 'Cancelado')],
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
	archivo_generado_nombre = fields.Char('Nombre de archivo', compute='_compute_archivo_generado_nombre')
	archivo_resultado = fields.Binary('Archivo resultado')
	cuota_fecha_hasta = fields.Date("Fecha vencimiento cuota hasta")
	fecha_generacion_archivo = fields.Date("Fecha generacion de archivo")
	cuota_ids = fields.Many2many('financiera.prestamo.cuota', 'financiera_bna_movimiento_cuota_rel', 'bna_movimiento_id', 'cuota_id', 'Cuotas')
	movimiento_linea_ids = fields.One2many('financiera.bna.debito.automatico.movimiento.linea','movimiento_id', 'Resultados')
	monto_debitado = fields.Float('Monto debitado', digits=(16,2))
	cantidad_registros_aplicados = fields.Integer('Registros aplicados')
	monto_no_debitado = fields.Float('Monto no debitado', digits=(16,2))
	cantidad_registros_no_aplicados = fields.Integer('Registros no aplicados')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.movimiento'))


	@api.one
	def _compute_name(self):
		self.name = 'Mes '+self.mes_tope_rendicion+' - Archivo '+self.nro_archivo_enviado_mes

	@api.one
	def _compute_archivo_generado_nombre(self):
		self.archivo_generado_nombre = 'DebitarBNA-Mes'+self.mes_tope_rendicion+'-Archivo'+self.nro_archivo_enviado_mes+'.txt'

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
		encabezado += "".ljust(94, ' ')
		encabezado += "\r\n"
		# Escribimos los registro tipo 2
		registros = ""
		total_a_debitar = 0
		for cuota_id in self.cuota_ids:
			if cuota_id.bna_debito_disponible:
				cuota_id.bna_debito_disponible = False
				registros += "2" 
				if cuota_id.debito_automatico_cuota_cbu.sucursal != False:
					sucursal = cuota_id.debito_automatico_cuota_cbu.sucursal.zfill(4)
					if len(sucursal) == 4:
						registros += sucursal
					else:
						raise ValidationError("Cuota "+str(cuota_id.name)+". La sucursal del banco no cumple los requerimientos.")
				else:
					raise ValidationError("Cuota "+str(cuota_id.name)+". La sucursal del banco no cumple los requerimientos.")
				# Hardcore CA - Supuestamente siempre sera CA: Caja de Ahorro
				registros += "CA"
				# Cuenta a debitar primera posicion 0 y N(10) para Nro de cuenta del cliente
				registros += "0"
				if cuota_id.debito_automatico_cuota_cbu.acc_number != False:
					acc_number = cuota_id.debito_automatico_cuota_cbu.acc_number.zfill(10)
					if len(acc_number) == 10:
						registros += acc_number
					else:
						raise ValidationError("El Nro de cuenta de la cuota "+str(cuota_id.name)+" no cumple los requerimientos.")
				else:
					raise ValidationError("El Nro de cuenta de la cuota "+str(cuota_id.name)+" no cumple los requerimientos.")
				# Importe a debitar N(15) 13,2
				if cuota_id.saldo > 0:
					saldo_lista = str(cuota_id.saldo).split(".")
					entera_string = saldo_lista[0]
					decimal_string = saldo_lista[1]
					if len(decimal_string) == 1:
						decimal_string += "0"
					registros += (entera_string+decimal_string).zfill(15)
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
				registros += "".ljust(46, ' ')
				registros += "\r\n"
			else:
				raise ValidationError("La cuota: "+str(cuota_id.name) + " no esta disponible para debito por cbu.")
		# Un Registro tipo 3
		finalizar = "3"
		# Importe total a debitar N(15) 13,2
		saldo_lista = str(total_a_debitar).split(".")
		entera_string = saldo_lista[0]
		decimal_string = saldo_lista[1]
		if len(decimal_string) == 1:
			decimal_string += "0"
		finalizar += (entera_string+decimal_string).zfill(15)
		# Cantidad de registros tipo 2 que se envian N(6)
		finalizar += str(len(self.cuota_ids)).zfill(6)
		# Empresa envia 0 N(15) - BNA devuelve monto no aplicado
		finalizar += "0".zfill(15)
		# Empresa envia 0 N(6) - BNA cant de reg. no aplicados
		finalizar += "0".zfill(6)
		# Agregamos blancos para cumplicar con los 128 bit a enviar
		finalizar += "".ljust(85, ' ')
		finalizar += "\r\n"
		
		file_read = base64.b64encode(encabezado+registros+finalizar)
		self.archivo_generado = file_read
		self.fecha_generacion_archivo = datetime.now()
		self.write({
			'state': 'generado',
		})

	@api.one
	def aplicar_archivo(self):
		if self.archivo_resultado == None:
			raise ValidationError('El archivo resultado no fue cargado')
		texto_resultado = self.archivo_resultado.decode('base64')
		registros = texto_resultado.split('\n')
		len_registros = len(registros)
		if len(registros[len_registros-1]) == 0:
			del registros[len_registros-1]
			len_registros -= 1
		monto_debitado = 0
		registros_aplicados = 0
		monto_no_debitado = 0
		registros_no_aplicados = 0
		i = 1
		for registro in registros:
			if len(registro) != 101:
				raise ValidationError("Error de longitud de registro en archivo de resultado.")
			else:
				# Comenzamos a analizar el registro
				if i == 1:
					# Es registro tipo 1
					if registro[0:1] != '1':
						raise ValidationError("El registro tipo 1 es incorrecto.")
					if registro[18:19] != 'D':
						raise ValidationError("El registro tipo 1 es incorrecto. BNA deberia devolver D como identificador.")
				elif i == len_registros:
					# Es registro tipo 3
					if registro[0:1] != '3':
						raise ValidationError("El registro tipo 3 es incorrecto.")
					parte_entera_string = registro[1:14]
					parte_decimal_string = registro[14:16]
					self.monto_debitado = float(parte_entera_string+"."+parte_decimal_string)
					self.cantidad_registros_aplicados = int(registro[16:22])
					parte_entera_string = registro[22:35]
					parte_decimal_string = registro[35:37]
					self.monto_no_debitado = float(parte_entera_string+"."+parte_decimal_string)
					self.cantidad_registros_no_aplicados = int(registro[37:43])
				else:
					# Es registro tipo 2
					if registro[0:1] != '2':
						raise ValidationError("El registro tipo 2 es incorrecto.")
					cr = self.env.cr
					uid = self.env.uid
					movimiento_line_obj = self.pool.get('financiera.bna.debito.automatico.movimiento.linea')
					_id = int(registro[72:82])
					if _id <= 0:
						raise ValidationError("Error en concepto debito de registro tipo 2.")
					linea_id = movimiento_line_obj.browse(cr, uid, _id)
					if linea_id != None and len(linea_id.movimiento_id) > 0 and linea_id.movimiento_id.id != self.id:
						raise ValidationError("Archivo incorrecto. No existe concepto a debitar.")
					if registro[41:42] == '0':
						# Debito aplicado.
						linea_id.state = 'cobrado'
						year_string = registro[33:37]
						month_string = registro[37:39]
						day_string = registro[39:41]
						fecha_string = year_string+"-"+month_string+"-"+day_string
						if int(year_string) <= 0 or int(month_string) <= 0 or int(day_string) <= 0:
							raise ValidationError("Fecha de cobro incorrecta en registro tipo 2.")
						linea_id.fecha_debito = datetime.strptime(fecha_string, "%Y-%m-%d")
						linea_id.monto_debitado = linea_id.monto_a_debitar
						monto_debitado += linea_id.monto_a_debitar
						registros_aplicados += 1
					elif registro[41:42] == '9':
						linea_id.state = 'rechazado'
						linea_id.descripcion = registro[42:72]
						linea_id.monto_no_debitado = linea_id.monto_a_debitar
						monto_no_debitado += linea_id.monto_a_debitar
						registros_no_aplicados += 1
						linea_id.cuota_id.bna_debito_disponible = True
			i += 1
		# if round(monto_debitado, 2) != round(self.monto_debitado, 2):
		# 	raise ValidationError("El monto debitado del registro 3 es inconcistente.")
		# if registros_aplicados != self.cantidad_registros_aplicados:
		# 	raise ValidationError("La cantidad de registros aplicados del registro 3 es inconcistente.")
		# if round(monto_no_debitado, 2) != round(self.monto_no_debitado, 2):
		# 	raise ValidationError("El monto no debitado del registro 3 es inconcistente.")
		# if registros_no_aplicados != self.cantidad_registros_no_aplicados:
		# 	raise ValidationError("La cantidad de registros aplicados del registro 3 es inconcistente.")
		self.write({
			'state': 'aplicado',
		})


	@api.one
	def enviar_a_cancelado(self):
		for cuota_id in self.cuota_ids:
			cuota_id.bna_debito_disponible = True
		for movimiento_line_id in self.movimiento_linea_ids:
			movimiento_line_id.state = 'cancelado'
			movimiento_line_id.fecha_debito = None
			movimiento_line_id.monto_debitado = 0
			movimiento_line_id.monto_no_debitado = 0
			movimiento_line_id.descripcion = None
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

	@api.multi
	def wizard_cobrar_movimiento(self):
		params = {
			'movimiento_id': self.id,
			'payment_amount': self.monto_debitado,
			'payment_date': self.fecha_generacion_archivo,
			'currency_id': self.env.user.company_id.currency_id.id,
		}
		view_id = self.env['financiera.bna.cobrar.wizard']
		new = view_id.create(params)
		domain = []
		context = dict(self._context or {})
		current_uid = context.get('uid')
		current_user = self.env['res.users'].browse(current_uid)
		for journal_id in current_user.entidad_login_id.journal_disponibles_ids:
			if journal_id.type in ('cash', 'bank'):
				domain.append(journal_id.id)
		context = {'domain': domain}
		return {
			'type': 'ir.actions.act_window',
			'name': 'Pagar prestamo',
			'res_model': 'financiera.bna.cobrar.wizard',
			'view_type': 'form',
			'view_mode': 'form',
			'res_id': new.id,
			'view_id': self.env.ref('financiera_bna_debito_automatico.bna_cobrar_wizard', False).id,
			'target': 'new',
			'context': context,
		}

	@api.one
	def confirmar_cobrar_movimiento(self, payment_date, journal_id,
			invoice, invoice_date, factura_electronica,
			punitorio_invoice, punitorio_invoice_date, punitorio_factura_electronica):
		if invoice:
			fpcmf_values = {
				'invoice_type': 'interes',
				'company_id': self.company_id.id,
			}
			multi_factura_id = self.env['financiera.prestamo.cuota.multi.factura'].create(fpcmf_values)
		if punitorio_invoice:
			fpcmf_values = {
				'invoice_type': 'punitorio',
				'company_id': self.company_id.id,
			}
			multi_factura_punitorio_id = self.env['financiera.prestamo.cuota.multi.factura'].create(fpcmf_values)
		for linea_id in self.movimiento_linea_ids:
			if linea_id.state == 'cobrado':
				cuota_id = linea_id.cuota_id
				partner_id = cuota_id.partner_id
				fpcmc_values = {
					'partner_id': partner_id.id,
					'company_id': self.company_id.id,
				}
				multi_cobro_id = self.env['financiera.prestamo.cuota.multi.cobro'].create(fpcmc_values)
				partner_id.multi_cobro_ids = [multi_cobro_id.id]
				cuota_id.confirmar_cobrar_cuota(payment_date, journal_id, linea_id.monto_debitado, multi_cobro_id)
				# Facturacion cuota
				if invoice:
					if not cuota_id.facturada:
						cuota_id.facturar_cuota(invoice_date, factura_electronica, multi_factura_id, multi_cobro_id)
				if cuota_id.punitorio_a_facturar > 0:
					cuota_id.facturar_punitorio_cuota(punitorio_invoice_date, punitorio_factura_electronica, multi_factura_punitorio_id, multi_cobro_id)
		if multi_factura_id.invoice_amount == 0:
			multi_factura_id.unlink()
		if multi_factura_punitorio_id.invoice_amount == 0:
			multi_factura_punitorio_id.unlink()
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
				('state', 'in', ('generado', 'aplicado', 'finalizado')),
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
	partner_id = fields.Many2one('res.partner', 'Cliente', related='cuota_id.partner_id')
	prestamo_id = fields.Many2one('financiera.prestamo', 'Prestamo', related='cuota_id.prestamo_id')
	monto_a_debitar = fields.Float('Monto a debitar', digits=(16,2))
	monto_debitado = fields.Float('Monto debitado', digits=(16,2))
	monto_no_debitado = fields.Float('Monto no debitado', digits=(16,2))
	descripcion = fields.Char('Descripcion del rechazo', size=30)
	fecha_debito = fields.Date('Fecha debito')
	state = fields.Selection(
		[('borrador', 'Borrador'),
		('cobrado', 'Cobrado'),
		('rechazado', 'Rechazado'),
		('cancelado', 'Cancelado')],
		string='Estado', default='borrador')
	company_id = fields.Many2one('res.company', 'Empresa', required=False, default=lambda self: self.env['res.company']._company_default_get('financiera.bna.debito.automatico.movimiento.linea'))

class ExtendsFinancieraPrestamo(models.Model):
	_name = 'financiera.prestamo'
	_inherit = 'financiera.prestamo'

	barrido_cbu_bna = fields.Boolean('Barrido por CBU Banco Nacion mediante archivo', compute='_compute_barrido_cbu_bna')
	debito_automatico_cuota = fields.Boolean('Barrido por CBU Banco Nacion', default=False)
	debito_automatico_cuota_cbu = fields.Many2one('res.partner.bank', 'CBU')

	@api.one
	def _compute_barrido_cbu_bna(self):
		self.barrido_cbu_bna = self.env.user.company_id.barrido_cbu_bna

	@api.onchange('debito_automatico_cuota')
	def _onchange_debito_automatico_cuota(self):
		for cuota_id in self.cuota_ids:
			cuota_id.debito_automatico_cuota = self.debito_automatico_cuota
		if self.debito_automatico_cuota:
			# Inabilitamos medios de pago incompatibles
			self.pagos360_pago_voluntario = False
		else:
			self.debito_automatico_cuota_cbu = False

	@api.onchange('debito_automatico_cuota_cbu')
	def _onchange_debito_automatico_cuota_cbu(self):
		for cuota_id in self.cuota_ids:
			cuota_id.debito_automatico_cuota_cbu = self.debito_automatico_cuota_cbu
			cuota_id.debito_bank_id = self.debito_automatico_cuota_cbu.bank_id.id


class ExtendsFinancieraPrestamoCuota(models.Model):
	_name = 'financiera.prestamo.cuota'
	_inherit = 'financiera.prestamo.cuota'

	bna_movimiento_ids = fields.Many2many('financiera.bna.debito.automatico.movimiento', 'financiera_bna_movimiento_cuota_rel', 'cuota_id', 'bna_movimiento_id', 'BNA debitos')
	bna_debito_automatico_linea_ids = fields.One2many('financiera.bna.debito.automatico.movimiento.linea', 'cuota_id', 'BNA resultados de debitos')
	bna_debito_disponible = fields.Boolean('Disponible para debito BNA?', default=True)


