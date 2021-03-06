# -*- coding: utf-8 -*-
# Copyright 2016 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import absolute_import
from __future__ import unicode_literals

import mock
import pytest
from data_pipeline.producer import Producer

from replication_handler.components.mysql_dump_handler import MySQLDumpHandler
from replication_handler.components.position_finder import PositionFinder
from replication_handler.components.recovery_handler import RecoveryHandler
from replication_handler.components.replication_stream_restarter import ReplicationStreamRestarter
from replication_handler.models.global_event_state import EventType
from replication_handler.models.global_event_state import GlobalEventState


class TestReplicationStreamRestarter(object):

    @pytest.fixture
    def producer(self):
        return mock.Mock(autospec=Producer)

    @pytest.fixture
    def mock_schema_wrapper(self):
        return mock.Mock()

    @pytest.yield_fixture
    def patch_get_global_event_state(self):
        with mock.patch.object(
            GlobalEventState,
            'get'
        ) as mock_get_global_event_state:
            yield mock_get_global_event_state

    @pytest.yield_fixture
    def patch_stream_reader(
        self,
    ):
        with mock.patch(
            'replication_handler.components.replication_stream_restarter.SimpleBinlogStreamReaderWrapper'
        ) as mock_stream_reader:
            yield mock_stream_reader

    @pytest.yield_fixture
    def patch_get_gtid_to_resume_tailing_from(self):
        with mock.patch.object(
            PositionFinder,
            'get_position_to_resume_tailing_from',
        ) as mock_get_gtid_to_resume_tailing_from:
            mock_get_gtid_to_resume_tailing_from.return_value = {}
            yield mock_get_gtid_to_resume_tailing_from

    @pytest.yield_fixture
    def patch_recover(self):
        with mock.patch.object(
            RecoveryHandler,
            'recover',
        ) as mock_recover:
            yield mock_recover

    @pytest.yield_fixture
    def mock_source_cursor(self):
        """ TODO(DATAPIPE-1525): This fixture override the
        `mock_source_cursor` fixture present in conftest.py
        """
        mock_cursor = mock.Mock()
        mock_cursor.fetchone.return_value = ('mysql-bin.000003', 1133)
        return mock_cursor

    @pytest.yield_fixture
    def patch_mysql_dump_exists(self):
        with mock.patch.object(
            MySQLDumpHandler,
            'mysql_dump_exists'
        ) as mock_handler:
            yield mock_handler

    def test_restart_with_clean_shutdown(
        self,
        producer,
        mock_db_connections,
        mock_schema_wrapper,
        patch_get_global_event_state,
        patch_stream_reader,
        patch_get_gtid_to_resume_tailing_from,
        patch_recover,
        patch_mysql_dump_exists
    ):
        patch_mysql_dump_exists.return_value = False
        next_event = mock.Mock()
        patch_stream_reader.return_value.next.return_value = next_event
        patch_get_global_event_state.return_value = mock.Mock(
            event_type=EventType.SCHEMA_EVENT,
            is_clean_shutdown=True
        )
        restarter = ReplicationStreamRestarter(
            mock_db_connections,
            mock_schema_wrapper,
            False
        )
        restarter.restart(producer)
        assert restarter.get_stream().next() == next_event
        assert patch_get_gtid_to_resume_tailing_from.call_count == 1
        assert patch_recover.call_count == 0

    def test_restart_with_unclean_shutdown(
        self,
        producer,
        mock_db_connections,
        mock_schema_wrapper,
        patch_get_global_event_state,
        patch_stream_reader,
        patch_get_gtid_to_resume_tailing_from,
        patch_recover,
        patch_mysql_dump_exists
    ):
        patch_mysql_dump_exists.return_value = True
        patch_get_global_event_state.return_value = mock.Mock(
            event_type=EventType.SCHEMA_EVENT,
            is_clean_shutdown=False
        )
        restarter = ReplicationStreamRestarter(
            mock_db_connections,
            mock_schema_wrapper,
            False
        )
        restarter.restart(producer)
        assert patch_get_gtid_to_resume_tailing_from.call_count == 1
        assert patch_recover.call_count == 1
