# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class SignSendRequest(models.TransientModel):
    _name = 'sign.send.request'
    _description = 'Sign send request'

    @api.model
    def default_get(self, fields):
        res = super(SignSendRequest, self).default_get(fields)
        res['template_id'] = self.env.context.get('active_id')
        template = self.env['sign.template'].browse(res['template_id'])
        res['filename'] = template.attachment_id.name
        res['subject'] = _("Signature Request - %s") % (template.attachment_id.name)
        roles = template.mapped('sign_item_ids.responsible_id')
        res['signers_count'] = len(roles)
        res['signer_ids'] = [(0, 0, {
            'role_id': role.id,
            'partner_id': False,
        }) for role in roles]
        return res

    template_id = fields.Many2one('sign.template', required=True, ondelete='cascade')
    signer_ids = fields.One2many('sign.send.request.signer', 'sign_send_request_id', string="Signers")
    signer_id = fields.Many2one('res.partner', string="Send To")
    signers_count = fields.Integer()
    follower_ids = fields.Many2many('res.partner', string="Copy to")
    extension = fields.Char(related="template_id.extension", readonly=False)
    is_user_signer = fields.Boolean(compute='_compute_is_user_signer')

    subject = fields.Char(string="Subject", required=True)
    message = fields.Html("Message")
    filename = fields.Char("Filename", required=True)

    @api.depends('template_id.attachment_id.datas_fname')
    def _compute_extension(self):
        for wizard in self.filtered(lambda w: w.template_id):
            wizard.extension = '.' + self.template_id.attachment_id.datas_fname.split('.')[-1]

    @api.depends('signer_ids.partner_id', 'signer_id', 'signers_count')
    def _compute_is_user_signer(self):
        if self.signers_count and self.env.user.partner_id in self.signer_ids.mapped('partner_id'):
            self.is_user_signer = True
        elif not self.signers_count and self.env.user.partner_id == self.signer_id:
            self.is_user_signer = True
        else:
            self.is_user_signer = False

    def create_request(self):
        template_id = self.template_id.id
        if self.signers_count:
            signers = [{'partner_id': signer.partner_id.id, 'role': signer.role_id.id} for signer in self.signer_ids]
        else:
            signers = [{'partner_id': self.signer_id.id, 'role': False}]
        followers = self.follower_ids.ids
        reference = self.filename
        subject = self.subject
        message = self.message
        return self.env['sign.request'].initialize_new(template_id, signers, followers, reference, subject, message, send=True)

    def send_request(self):
        res = self.create_request()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signature(s)'),
            'view_mode': 'form',
            'res_model': 'sign.request',
            'res_id': res['id']
        }

    def sign_directly(self):
        res = self.create_request()
        request = self.env['sign.request'].browse(res['id'])
        user_item = request.request_item_ids.filtered(
            lambda item: item.partner_id == item.env.user.partner_id)[:1]
        return {
            'type': 'ir.actions.client',
            'tag': 'sign.SignableDocument',
            'name': _('Sign'),
            'context': {
                'id': request.id,
                'token': user_item.access_token,
                'sign_token': user_item.access_token,
                'create_uid': request.create_uid.id,
                'state': request.state,
            },
        }


class SignSendRequestSigner(models.TransientModel):
    _name = "sign.send.request.signer"
    _description = 'Sign send request signer'

    role_id = fields.Many2one('sign.item.role', readonly=True)
    partner_id = fields.Many2one('res.partner', required=True)
    sign_send_request_id = fields.Many2one('sign.send.request')
