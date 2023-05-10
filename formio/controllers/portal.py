# Copyright Nova Code (http://www.novacode.nl)
# See LICENSE file for full licensing details.

import json
import logging

from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.formio_builder import STATE_CURRENT as BUILDER_STATE_CURRENT

from ..models.formio_form import (
    STATE_DRAFT as FORM_STATE_DRAFT,
    STATE_COMPLETE as FORM_STATE_COMPLETE,
)

_logger = logging.getLogger(__name__)


class FormioCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'form_count' in counters:
            domain = [('user_id', '=', request.env.user.id), ('builder_id.portal', '=', True)]
            values['form_count'] = (
                request.env['formio.form'].search_count(domain)
                if request.env['formio.form'].check_access_rights('read', raise_exception=False)
                else 0
            )
        return values

    def _formio_form_prepare_portal_layout_values(self, **kwargs):
        values = super(FormioCustomerPortal, self)._prepare_portal_layout_values()

        # TODO create model (class)method for this?
        domain = [
            ('portal', '=', True),
            ('formio_res_model_id', '=', False),
            ('state', '=', BUILDER_STATE_CURRENT)
        ]
        # TODO order by sequence?
        order = 'name ASC'
        builders_create_form = request.env['formio.builder'].search(domain, order=order)
        values.update({
            'builders_create_form': builders_create_form,
            'page_name': 'formio',
            'default_url': '/my/formio'
        })

        # Forms
        res_model = kwargs.get('res_model')
        res_id = kwargs.get('res_id')
        if res_model and res_id:
            domain = [
                ('res_model', '=', res_model),
                ('res_id', '=', res_id),
                ('user_id', '=', request.env.user.id),
                ('builder_id.portal', '=', True)
            ]
            forms = request.env['formio.form'].search(domain)
            if forms:
                values['res_model'] = res_model
                values['res_id'] = res_id
                values['res_name'] = forms[0].res_id
                values['form_count'] = len(forms)
        else:
            domain = [('user_id', '=', request.env.user.id), ('builder_id.portal', '=', True)]
            values['form_count'] = request.env['formio.form'].search_count(domain)
        return values

    def _formio_form_get_page_view_values(self, form, **kwargs):
        values = {
            'form': form,
            'page_name': 'formio',
        }
        return self._get_page_view_values(form, False, values, 'my_formio', False, **kwargs)

    def _formio_form_new_get_page_view_values(self, builder, **kwargs):
        values = {
            'builder': builder,
            'page_name': 'formio',
        }
        return self._get_page_view_values(builder, False, values, 'my_formio', False, **kwargs)

    def _get_form(self, uuid, mode):
        return request.env['formio.form'].get_form(uuid, mode)

    def _redirect_url(self, **kwargs):
        res_model = kwargs.get('res_model')
        res_id = kwargs.get('res_id')
        if res_model and res_id:
            return '/my/formio?res_model=%s&res_id=%s' % (res_model, res_id)
        else:
            return '/my/formio'

    ####################
    # Form - portal list
    ####################

    @http.route(['/my/formio'], type='http', auth="user", website=True)
    def portal_forms(self, sortby=None, search=None, search_in='content',  **kwargs):
        domain = [
            ('user_id', '=', request.env.user.id),
            ('portal_share', '=', True)
        ]
        res_model = kwargs.get('res_model')
        res_id = kwargs.get('res_id')
        if res_model and res_id:
            domain.append(('res_model', '=', res_model))
            domain.append(('res_id', '=', res_id))
        
        order = 'create_date DESC'
        forms = request.env['formio.form'].search(domain, order=order)

        values = self._formio_form_prepare_portal_layout_values(**kwargs)
        values['forms'] = forms
        return request.render("formio.portal_my_formio", values)

    ###############################
    # Form - portal create and uuid
    ###############################

    @http.route('/my/formio/form/<string:uuid>', type='http', auth='user', website=True)
    def portal_form(self, uuid, **kwargs):
        form = self._get_form(uuid, 'read')
        if not form:
            # TODO website page with message?
            return request.redirect("/")

        values = self._formio_form_get_page_view_values(form, **kwargs)
        return request.render("formio.portal_my_formio_edit", values)

    @http.route(['/my/formio/form/create/<string:name>'], type='http', auth="user", methods=['GET'], website=True)
    def portal_create_form(self, name):
        builder = request.env['formio.builder'].search([('name', '=', name), ('portal', '=', True)], limit=1)
        if not builder:
            redirect_url = self._redirect_url()
            # TODO website page with message?
            return request.redirect(redirect_url)
        vals = {
            'builder_id': builder.id,
            'title': builder.title,
            'user_id': request.env.user.id,
            'partner_id': request.env.user.partner_id.id
        }
        form = request.env['formio.form'].create(vals)
        url = '/my/formio/form/{uuid}'.format(uuid=form.uuid)
        return request.redirect(url)

    @http.route(['/my/formio/form/<string:uuid>/delete'], type='http', auth="user", methods=['GET'], website=True)
    def portal_delete_form(self, uuid, **kwargs):
        """ Unlink form. Access rules apply on the unlink method """

        form = request.env['formio.form'].get_form(uuid, 'unlink')
        redirect_url = self._redirect_url(**kwargs)
        if not form:
            # TODO call method (website_formio page) with message?
            return request.redirect(redirect_url)
        form.unlink()
        # TODO call method (website_formio page) with message?

        return request.redirect(redirect_url)

    @http.route(['/my/formio/form/<string:uuid>/cancel'], type='http', auth="user", methods=['GET'], website=True)
    def portal_cancel_form(self, uuid, **kwargs):
        """ Cancel form. Access rules apply on the write method """

        form = request.env['formio.form'].get_form(uuid, 'write')
        redirect_url = self._redirect_url(**kwargs)
        if not form:
            # TODO call method (website_formio page) with message?
            return request.redirect(redirect_url)
        form.action_cancel()
        # TODO call method (website_formio page) with message?
        return request.redirect(redirect_url)

    @http.route(['/my/formio/form/<string:uuid>/copy'], type='http', auth="user", methods=['GET'], website=True)
    def portal_copy_form(self, uuid, **kwargs):
        form = request.env['formio.form'].get_form(uuid, 'read')
        redirect_url = self._redirect_url(**kwargs)
        if not form:
            # TODO call method (website_formio page) with message?
            return request.redirect(redirect_url)
        form.action_copy()
        # TODO call method (website_formio page) with message?

        return request.redirect(redirect_url)

    ###################
    # Form - portal new
    ###################

    @http.route('/my/formio/form/new/<string:builder_name>', type='http', auth='user', website=True)
    def portal_form_new(self, builder_name, **kwargs):
        builder = self._get_builder_name(builder_name)
        if not builder:
            msg = 'Form Builder (name) %s: not found' % builder_name
            return request.not_found(msg)
        elif not builder.portal:
            msg = 'Form Builder (name) %s: not published on portal' % builder_name
            return request.not_found(msg)

        values = self._formio_form_new_get_page_view_values(builder, **kwargs)
        return request.render("formio.portal_my_formio_new", values)

    @http.route('/formio/portal/form/new/<string:builder_name>', type='http', auth='user', methods=['GET'], website=True)
    def portal_form_new_root(self, builder_name, **kwargs):
        builder = self._get_builder_name(builder_name)
        if not builder:
            msg = 'Form Builder (name) %s: not found' % builder_name
            return request.not_found(msg)
        elif not builder.portal:
            msg = 'Form Builder (name) %s: not published on portal' % builder_name
            return request.not_found(msg)

        values = {
            'builder': builder,
            # 'languages' already injected in rendering somehow
            'form_languages': builder.languages,
            'formio_builder_uuid': builder.uuid,
            'formio_css_assets': builder.formio_css_assets,
            'formio_js_assets': builder.formio_js_assets,
            'extra_assets': builder.extra_asset_ids
        }
        return request.render('formio.formio_form_portal_new_embed', values)

    @http.route('/formio/portal/form/new/<string:builder_uuid>/config', type='json', auth='user', website=True)
    def form_new_config(self, builder_uuid, **kwargs):
        builder = self._get_builder_uuid(builder_uuid)
        res = {'schema': {}, 'options': {}, 'params': {}}

        if not builder or builder.state != BUILDER_STATE_CURRENT:
            return res

        if builder.schema:
            res['schema'] = json.loads(builder.schema)
            res['options'] = self._get_form_js_options(builder)
            res['locales'] = self._get_form_js_locales(builder)
            res['params'] = self._get_form_js_params(builder)

        args = request.httprequest.args
        etl_odoo_config = builder.sudo()._etl_odoo_config(params=args.to_dict())
        res['options'].update(etl_odoo_config.get('options', {}))
        return res

    @http.route('/formio/portal/form/new/<string:builder_uuid>/submission', type='json', auth='user', website=True)
    def form_new_submission(self, builder_uuid, **kwargs):
        builder = self._get_builder_uuid(builder_uuid)

        if not builder:
            _logger.info('formio.builder with UUID %s not found' % builder_uuid)
            # TODO raise or set exception (in JSON resonse) ?
            return

        args = request.httprequest.args
        submission_data = {}
        etl_odoo_data = builder.sudo()._etl_odoo_data(params=args.to_dict())
        submission_data.update(etl_odoo_data)
        return json.dumps(submission_data)

    @http.route('/formio/portal/form/new/<string:builder_uuid>/submit', type='json', auth="user", methods=['POST'], website=True)
    def form_new_submit(self, builder_uuid, **post):
        """ Form submit endpoint

        Note:
        In wizard mode, the submit endpoint shall be changed
        (frontend/JS code) to: /formio/form/<string:uuid>/submit
        """
        builder = self._get_builder_uuid(builder_uuid)

        if not builder:
            # TODO raise or set exception (in JSON resonse) ?
            return

        Form = request.env['formio.form']
        vals = {
            'builder_id': builder.id,
            'title': builder.title,
            'submission_data': json.dumps(post['data']),
            'submission_date': fields.Datetime.now(),
            'submission_user_id': request.env.user.id,
            'user_id': request.env.user.id,
            'portal_share': True
        }

        save_draft = post.get('saveDraft') or (post['data'].get('saveDraft') and not post['data'].get('submit'))

        if save_draft:
            vals['state'] = FORM_STATE_DRAFT
        else:
            vals['state'] = FORM_STATE_COMPLETE

        context = {'tracking_disable': True}
        res = Form.with_context(**context).create(vals)

        if vals.get('state') == FORM_STATE_COMPLETE:
            res.after_submit()
        request.session['formio_last_form_uuid'] = res.uuid
        return {'form_uuid': res.uuid}

    #########
    # Helpers
    #########

    def _get_builder_uuid(self, builder_uuid):
        return request.env['formio.builder'].get_portal_builder_uuid(builder_uuid)

    def _get_builder_name(self, builder_name):
        return request.env['formio.builder'].get_portal_builder_name(builder_name)

    def _get_form_js_options(self, builder):
        options = {
            'embedded': True,
            'i18n': builder.i18n_translations()
        }

        # language
        Lang = request.env['res.lang']
        if request.context.get('lang'):
            options['language'] = Lang._formio_ietf_code(request.context.get('lang'))
        elif request.env.user.lang:
            options['language'] = Lang._formio_ietf_code(request.env.user.lang)
        else:
            options['language'] = request.env.ref('base.lang_en').formio_ietf_code

        return options

    def _get_form_js_locales(self, builder):
        return builder._get_form_js_locales()

    def _get_form_js_params(self, builder):
        return builder._get_portal_form_js_params()
