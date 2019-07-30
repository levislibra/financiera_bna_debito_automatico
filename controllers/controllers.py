# -*- coding: utf-8 -*-
from openerp import http

# class FinancieraBnaDebitoAutomatico(http.Controller):
#     @http.route('/financiera_bna_debito_automatico/financiera_bna_debito_automatico/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/financiera_bna_debito_automatico/financiera_bna_debito_automatico/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('financiera_bna_debito_automatico.listing', {
#             'root': '/financiera_bna_debito_automatico/financiera_bna_debito_automatico',
#             'objects': http.request.env['financiera_bna_debito_automatico.financiera_bna_debito_automatico'].search([]),
#         })

#     @http.route('/financiera_bna_debito_automatico/financiera_bna_debito_automatico/objects/<model("financiera_bna_debito_automatico.financiera_bna_debito_automatico"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('financiera_bna_debito_automatico.object', {
#             'object': obj
#         })