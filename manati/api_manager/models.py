#
# Copyright (c) 2017 Stratosphere Laboratory.
#
# This file is part of ManaTI Project
# (see <https://stratosphereips.org>). It was created by 'Raul B. Netto <raulbeni@gmail.com>'
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. See the file 'docs/LICENSE' or see <http://www.gnu.org/licenses/>
# for copying permission.
#
from __future__ import unicode_literals

from django.db import models
from manati.analysis_sessions.models import TimeStampedModel, IOC, AnalysisSession
from model_utils.fields import AutoCreatedField,AutoLastModifiedField
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from model_utils import Choices
import json


class ExternalModuleManager(models.Manager):

    def create(self, module_instance, filename, module_name, description, version, authors, available_events, *args, **kwargs):
        external_module_obj = ExternalModule()
        external_module_obj.module_instance = module_instance
        external_module_obj.filename = filename
        external_module_obj.module_name = module_name
        external_module_obj.description = description
        external_module_obj.version = version
        external_module_obj.authors = authors
        for event in available_events:
            # if event innot dict(self.VERDICT_STATUS):
            external_module_obj.MODULES_RUN_EVENTS[event]
        external_module_obj.run_in_events = json.dumps(available_events)
        external_module_obj.status = ExternalModule.MODULES_STATUS.idle
        external_module_obj.clean()
        external_module_obj.save()

    def find_idle_modules_by_event(self, event_name):
        return ExternalModule.objects.filter(run_in_events__contains=event_name,
                                             status=ExternalModule.MODULES_STATUS.idle).distinct()

    def find_by_event(self, event_name):
        ets= ExternalModule.objects.filter(run_in_events__contains=event_name)\
            .exclude(status=ExternalModule.MODULES_STATUS.removed).distinct()
        etss = []
        for et in ets:
            run_in_events = json.loads(et.run_in_events)
            if event_name in run_in_events:
                etss.append(et)
        return etss


class ExternalModule(TimeStampedModel):
    MODULES_RUN_EVENTS = Choices('labelling', 'bulk_labelling', 'labelling_malicious', 'after_save', 'by_request')
    MODULES_STATUS = Choices('idle', 'running', 'removed')
    module_instance = models.CharField(max_length=50, unique=True)
    module_name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    version = models.CharField(max_length=30)
    authors = JSONField(default=json.dumps({}))
    run_in_events = JSONField(default=json.dumps({}))
    filename = models.CharField(max_length=50, null=True)
    status = models.CharField(max_length=20, choices=MODULES_STATUS, default=MODULES_STATUS.idle)

    objects = ExternalModuleManager()

    def set_status(self, status):
        pass

    def get_events(self):
        return json.loads(self.run_in_events)

    def has_event(self, event):
        available_event = self.get_events()
        return event in available_event

    def mark_idle(self, save=False):
        self.status = self.MODULES_STATUS.idle
        # hem = HistoryExternalModule.objects.last()
        # hem.save()
        if save:
            self.save()

    def mark_running(self, save=False):
        self.status = self.MODULES_STATUS.running
        # HistoryExternalModule.objects.create()
        if save:
            self.save()

    class Meta:
        db_table = 'manati_externals_modules'


class IOC_WHOIS_RelatedExecuted(TimeStampedModel):
    ioc = models.ForeignKey(IOC, related_name='whois_relation_executions')
    analysis_session = models.ForeignKey(AnalysisSession)
    MODULES_STATUS = Choices('finished', 'running', 'removed', 'error')
    status = models.CharField(max_length=20, choices=MODULES_STATUS, default=MODULES_STATUS.running)

    @staticmethod
    def relation_perfomed_by_domain(analysis_session_id, domain):
        return IOC_WHOIS_RelatedExecuted.objects.filter(analysis_session_id=analysis_session_id,
                                                 ioc__value=domain,
                                                 ioc__ioc_type=IOC.IOC_TYPES.domain).exists()

    @staticmethod
    def finished(analysis_session_id, domain):
        return IOC_WHOIS_RelatedExecuted.objects.filter(analysis_session_id=analysis_session_id,
                                                        status= IOC_WHOIS_RelatedExecuted.MODULES_STATUS.finished,
                                                        ioc__value=domain,
                                                        ioc__ioc_type=IOC.IOC_TYPES.domain).exists()

    @staticmethod
    def started(analysis_session_id, domain):
        return IOC_WHOIS_RelatedExecuted.objects.filter(analysis_session_id=analysis_session_id,
                                                        status=IOC_WHOIS_RelatedExecuted.MODULES_STATUS.running,
                                                        ioc__value=domain,
                                                        ioc__ioc_type=IOC.IOC_TYPES.domain).exists()
    @staticmethod
    def start(analysis_session_id, domain):
        ioc = IOC.objects.get(value=domain,ioc_type=IOC.IOC_TYPES.domain)
        if IOC_WHOIS_RelatedExecuted.started(analysis_session_id, domain):
            raise Exception("You cannot start again this module for "+analysis_session_id+" while is running")
        elif IOC_WHOIS_RelatedExecuted.finished(analysis_session_id, domain):
            iwre = IOC_WHOIS_RelatedExecuted.objects.get(analysis_session_id=analysis_session_id, ioc_id=ioc.id)
            iwre.status = IOC_WHOIS_RelatedExecuted.MODULES_STATUS.running
            iwre.save()
        else:
            IOC_WHOIS_RelatedExecuted.objects.create(analysis_session_id=analysis_session_id,
                                                 ioc=ioc, status=IOC_WHOIS_RelatedExecuted.MODULES_STATUS.running)

    @staticmethod
    def finish(analysis_session_id, domain):
        ioc = IOC.objects.get(value=domain,ioc_type=IOC.IOC_TYPES.domain)
        iwr = IOC_WHOIS_RelatedExecuted.objects.get(analysis_session_id=analysis_session_id, ioc=ioc)
        iwr.status = IOC_WHOIS_RelatedExecuted.MODULES_STATUS.finished
        iwr.save()

    @staticmethod
    def mark_error(analysis_session_id, domain):
        ioc = IOC.objects.get(value=domain, ioc_type=IOC.IOC_TYPES.domain)
        iwr = IOC_WHOIS_RelatedExecuted.objects.get(analysis_session_id=analysis_session_id, ioc=ioc)
        iwr.status = IOC_WHOIS_RelatedExecuted.MODULES_STATUS.error
        iwr.save()


    class Meta:
        db_table = 'manati_ioc_whois_related_executed'
