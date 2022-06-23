# Copyright Nova Code (http://www.novacode.nl)
# See LICENSE file for full licensing details.

import logging

from formiodata.components import datagridComponent

from odoo import fields, models, api, tools, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FormioBuilder(models.Model):
    _inherit = 'formio.builder'

    component_sync_active = fields.Boolean(
        default=True,
        string='Synchronize Components'
    )
    component_ids = fields.One2many(
        comodel_name="formio.component",
        inverse_name="builder_id",
        string="Components"
    )

    @api.constrains("builder_id", "component_id")
    def constraint_unique_builder_component_id(self):
        res = self.search([
            ("builder_id", "=", self.builder_id.id),
            ("component_id", "=", self.component_id.id)
        ])
        if len(res) > 1:
            raise ValidationError(_('Builder and Component ID should be unique!'))

    def write(self, vals):
        res = super(FormioBuilder, self).write(vals)
        if vals.get('schema') and self.component_sync_active:
            self.synchronize_formio_components()
        return res

    # ----------------------------------------------------------
    # Helper
    # ----------------------------------------------------------

    def _get_component(self, comp_id):
        """
        Returns a formio.component obj from component_id.
        """
        return self.env['formio.component'].search([
            ("builder_id", '=', self.id),
            ("component_id", '=', comp_id)
        ], limit=1)

    def _compare_components(self):
        """
        Compares arrays with component keys.
        """
        new_components = []
        old_components = []
        for comp_id, obj in self._formio.component_ids.items():
            new_components.append(comp_id)
        for record in self.env['formio.component'].search([("builder_id", 'in', self.ids)]):
            old_components.append(record.component_id)
        return {
            'added': list(set(new_components).difference(old_components)),
            'deleted': list(set(old_components).difference(new_components))
        }

    def _write_components(self, comp_ids):
        """
        Writes the components with all required data to formio.component model.
        """
        for comp_id in comp_ids:
            try:
                obj = self._formio.component_ids[comp_id]
            except KeyError as e:
                msg = _('No component found with (generated) id %s in the Form Builder.\n\n'
                        'Suggestion:\nOpen the Form Builder and add or edit a component (eg label, setting), which generates new component ids.') % comp_id
                raise ValidationError(msg)

            self.env['formio.component'].create({
                'label': obj.label,
                'component_id': obj.id,
                'key': obj.key,
                'type': obj.type,
                'builder_id': self.id,
            })

    def _update_components(self):
        """
        Checks for any component related changes and synchronize them with database records.
        """
        for comp_id, obj in self._formio.component_ids.items():
            record = self._get_component(comp_id)
            if not record or record.component_id != obj.id:
                continue

            """
            Updating component attributes
            """
            if record.label != obj.label:
                record.label = obj.label
            if record.key != obj.key:
                record.key = obj.key

            """
            Updating parent_id
            """
            if obj.parent:
                parent_id = False
                if isinstance(obj.parent, datagridComponent.gridRow):
                    for datagrid_id, datagrid in self._formio.component_ids.items():
                        if datagrid.type == 'datagrid':
                            for row in datagrid.rows:
                                for key in row.input_components:
                                    comp = row.input_components[key]
                                    if comp.id == obj.id:
                                        parent_id = datagrid.id
                else:
                    parent_id = obj.parent.id
                if record.parent_id.component_id != parent_id:
                    parent_record = self._get_component(parent_id)
                    record.parent_id = parent_record
            elif not obj.parent and record.parent_id:
                record.parent_id = False

    def _delete_components(self, comp_ids):
        """
        Removes components from formio.component model.
        """
        for comp_id in comp_ids:
            components = self._get_component(comp_id)
            components.unlink()

    # ----------------------------------------------------------
    # Public
    # ----------------------------------------------------------

    def synchronize_formio_components(self):
        """
        Synchronize builder components with the formio.component model.
        """
        components_dict = self._compare_components()
        if components_dict['added']:
            self._write_components(components_dict['added'])
        if components_dict['deleted']:
            self._delete_components(components_dict['deleted'])
        self._update_components()
