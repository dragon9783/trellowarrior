#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2015-2020 Óscar García Amor <ogarcia@connectical.com>
#
# Distributed under terms of the GNU GPLv3 license.

from trellowarrior.clients.taskwarrior import TaskwarriorClient
from trellowarrior.clients.trello import TrelloClient
from trellowarrior.config import config

import logging

logger = logging.getLogger(__name__)

class TrelloWarriorClient:
    def __init__(self, config):
        self.taskwarrior_client = TaskwarriorClient(config.taskwarrior_taskrc_location, config.taskwarrior_data_location)
        self.trello_client = TrelloClient(config.trello_api_key, config.trello_api_secret, config.trello_token, config.trello_token_secret)

    def upload_taskwarrior_task(self, taskwarrior_task, trello_list):
        """
        Upload all contents of Taskwarrior task to a Trello list creating a new card and storing cardid

        :param taskwarrior_task: Taskwarrior task object
        :param trello_list: Trello list object
        """
        new_trello_card = trello_list.add_card(taskwarrior_task['description'])
        if taskwarrior_task['due']:
            new_trello_card.set_due(taskwarrior_task['due'])
        taskwarrior_task['trelloid'] = new_trello_card.id
        taskwarrior_task.save()

    def fetch_trello_card(self, project, list_name, trello_card):
        """
        Fetch contents of a Trello card to a new Taskwarrior task

        :param project: TrelloWarrior project object
        :list_name: name of the Trello list where the card is stored
        :param trello_card: Trello card object
        """
        new_taskwarrior_task = self.taskwarrior_client.new_task()
        new_taskwarrior_task['project'] = project.project_name
        new_taskwarrior_task['description'] = trello_card.name
        if trello_card.due_date:
            new_taskwarrior_task['due'] = trello_card.due_date
        new_taskwarrior_task['trelloid'] = trello_card.id
        new_taskwarrior_task['trellolistname'] = list_name
        new_taskwarrior_task.save()
        logger.info('Trello card with ID {} saved as new task in Taskwarrior with ID {}'.format(trello_card.id, new_taskwarrior_task['id']))
        if list_name == project.trello_doing_list:
            new_taskwarrior_task.start()
            logger.info('New task {} kicked to doing list'.format(new_taskwarrior_task['id']))
        if list_name == project.trello_done_list:
            new_taskwarrior_task.done()
            logger.info('New task {} kicked to done list'.format(new_taskwarrior_task['id']))

    def sync_task_card(self, project, trello_lists, list_name, trello_card, taskwarrior_task):
        """
        Sync an existing Taskwarrior task with an existing Trello card

        :param project: TrelloWarrior project object
        :param trello_lists: list of Trello lists objects
        :param list_name: name of the Trello list where the card is stored
        :param trello_card: Trello card object
        :param taskwarrior_task: Taskwarrior task object
        """
        taskwarrior_task_modified = False # Change to true to save modification
        # Task description <> Trello card name
        if taskwarrior_task['description'] != trello_card.name:
            if taskwarrior_task['modified'] > trello_card.date_last_activity:
                # Taskwarrior data is newer
                trello_card.set_name(taskwarrior_task['description'])
            else:
                # Trello data is newer
                taskwarrior_task['description'] = trello_card.name
                taskwarrior_task_modified = True
            logger.info('Name of task {} synchronized'.format(taskwarrior_task['id']))
        # Task due <> Trello due
        if taskwarrior_task['due']:
            if not trello_card.due_date or taskwarrior_task['modified'] > trello_card.date_last_activity:
                # No due data in Trello or Taskwarrior data is newer
                trello_card.set_due(taskwarrior_task['due'])
            else:
                # Trello data is newer
                taskwarrior_task['due'] = trello_card.due_date
                taskwarrior_task_modified = True
            logger.info('Due date of task {} synchronized'.format(taskwarrior_task['id']))
        elif trello_card.due_date:
            # No due data in Taskwarrior
            taskwarrior_task['due'] = trello_card.due_date
            taskwarrior_task_modified = True
            logger.info('Due date of task {} synchronized'.format(taskwarrior_task['id']))
        # Task list name and status <> Trello list name
        if taskwarrior_task.pending and not taskwarrior_task.active and taskwarrior_task['trellolistname'] in [project.trello_doing_list, project.trello_done_list] and taskwarrior_task['modified'] > trello_card.date_last_activity:
            # Task kicked to To Do in Taskwarrior and not synchronized
            trello_card.change_list(self.trello_client.get_trello_list(project.trello_board_name, trello_lists, project.trello_todo_list).id)
            taskwarrior_task['trellolistname'] = list_name = project.trello_todo_list
            taskwarrior_task_modified = True
            logger.info('Task {} kicked to todo list in Trello'.format(taskwarrior_task['id']))
        if taskwarrior_task.active and taskwarrior_task['trellolistname'] != project.trello_doing_list and taskwarrior_task['modified'] > trello_card.date_last_activity:
            # Task kicked to doing in Taskwarrior and not synchronized
            trello_card.change_list(self.trello_client.get_trello_list(project.trello_board_name, trello_lists, project.trello_doing_list).id)
            taskwarrior_task['trellolistname'] = list_name = project.trello_doing_list
            taskwarrior_task_modified = True
            logger.info('Task {} kicked to doing list in Trello'.format(taskwarrior_task['id']))
        if taskwarrior_task.completed and taskwarrior_task['trellolistname'] != project.trello_done_list and taskwarrior_task['modified'] > trello_card.date_last_activity:
            # Task kicked to doing in Taskwarrior and not synchronized
            trello_card.change_list(self.trello_client.get_trello_list(project.trello_board_name, trello_lists, project.trello_done_list).id)
            taskwarrior_task['trellolistname'] = list_name = project.trello_done_list
            taskwarrior_task_modified = True
            logger.info('Task {} kicked to done list in Trello'.format(taskwarrior_task['id']))
        if taskwarrior_task['trellolistname'] != list_name:
            if taskwarrior_task['modified'] > trello_card.date_last_activity:
                # Taskwarrior data is newer
                trello_card.change_list(self.trello_client.get_trello_list(project.trello_board_name, trello_lists, taskwarrior_task['trellolistname']).id)
                logger.info('Task {} kicked to {} list in Trello'.format(taskwarrior_task['id'], taskwarrior_task['trellolistname']))
            else:
                # Trello data is newer
                taskwarrior_task['trellolistname'] = list_name
                if list_name == project.trello_done_list and not taskwarrior_task.completed:
                    taskwarrior_task.save() # Must save before a status change to avoid data loss
                    taskwarrior_task.done()
                    logger.info('Task {} kicked to done list in Taskwarrior'.format(taskwarrior_task['id']))
                elif list_name == project.trello_doing_list:
                    if taskwarrior_task.completed:
                        taskwarrior_task['status'] = 'pending'
                        taskwarrior_task.save()
                        taskwarrior_task.start()
                    elif not taskwarrior_task.active:
                        taskwarrior_task.save()
                        taskwarrior_task.start()
                    else:
                        taskwarrior_task.save()
                    logger.info('Task {} kicked to doing list in Taskwarrior'.format(taskwarrior_task['id']))
                else:
                    if taskwarrior_task.completed:
                        taskwarrior_task['status'] = 'pending'
                        taskwarrior_task.save()
                    elif taskwarrior_task.active:
                        taskwarrior_task.save()
                        taskwarrior_task.stop()
                    else:
                        taskwarrior_task.save()
                    logger.info('Task {} kicked to {} list in Taskwarrior'.format(taskwarrior_task['id'], taskwarrior_task['trellolistname']))
                taskwarrior_task_modified = False # Avoid save again
                logger.info('All changes in Taskwarrior task {} saved'.format(taskwarrior_task['id']))
        # Save Taskwarrior changes (if any)
        if taskwarrior_task_modified:
            taskwarrior_task.save()
            logger.info('All changes in Taskwarrior task {} saved'.format(taskwarrior_task['id']))

    def sync_project(self, project):
        """
        Sync a Taskwarrior project with a Trello board

        :param project: TrelloWarrior project object
        """
        # Get all Taskwarrior deleted tasks and seek for ones that have trelloid (deleted in Taskwarrior)
        logger.info('Syncing project {} step 1: delete Trello cards that already deleted in Taskwarrior'.format(project.project_name))
        taskwarrior_deleted_tasks = self.taskwarrior_client.get_deleted_tasks(project.project_name)
        for taskwarrior_deleted_task in taskwarrior_deleted_tasks:
            if taskwarrior_deleted_task['trelloid']:
                logger.info('Deleting previously deleted Taskwarrior task with ID {} from Trello'.format(taskwarrior_deleted_task['trelloid']))
                self.trello_client.delete_trello_card(taskwarrior_deleted_task['trelloid'])
                taskwarrior_deleted_task['trelloid'] = None
                taskwarrior_deleted_task.save()
        # Compare and sync Taskwarrior with Trello
        logger.info('Syncing project {} step 2: syncing changes between Taskwarrior and Trello'.format(project.project_name))
        trello_lists = self.trello_client.get_trello_lists(project.trello_board_name)
        trello_cards_dict = self.trello_client.get_trello_cards_dict(trello_lists, project.trello_lists_filter)
        trello_cards_ids = [] # List to store cards IDs to compare later with local trelloid
        for trello_list_name in trello_cards_dict:
            for trello_card in trello_cards_dict[trello_list_name]:
                # Fech all data from card
                trello_card.fetch(False) # Pass False to fetch to avoid download attachments
                trello_cards_ids.append(trello_card.id)
                taskwarrior_task = self.taskwarrior_client.get_task_by_trello_id(trello_card.id)
                if taskwarrior_task is None:
                    # Download new Trello card that not present in Taskwarrior
                    logger.info('Downloading Trello card with ID {} as new task in Taskwarrior'.format(trello_card.id))
                    self.fetch_trello_card(project, trello_list_name, trello_card)
                else:
                    # Sync Taskwarrior task with Trello card
                    self.sync_task_card(project, trello_lists, trello_list_name, trello_card, taskwarrior_task)
        # Compare Trello and Taskwarrior tasks for remove deleted Trello tasks in Taskwarrior
        logger.info('Syncing project {} step 3: delete Takswarrior tasks that already deleted in Trello'.format(project.project_name))
        taskwarrior_tasks_ids = self.taskwarrior_client.get_tasks_ids_set(project.project_name)
        taskwarrior_tasks_ids.discard(None) # Remove None element if present (new tasks created with Taskwarrior)
        trello_cards_ids = set(trello_cards_ids) # Convert trello_cards_ids list in a set
        for deleted_trello_task_id in taskwarrior_tasks_ids - trello_cards_ids:
            taskwarrior_task_to_delete = self.taskwarrior_client.get_task_by_trello_id(deleted_trello_task_id)
            taskwarrior_task_to_delete['trelloid'] = None
            taskwarrior_task_to_delete.save()
            taskwarrior_task_to_delete.delete()
            logger.info('Deleting previously deleted Trello task with ID {} from Taskwarrior'.format(deleted_trello_task_id))
        # Upload new Taskwarrior tasks that never uploaded before
        logger.info('Syncing project {} step 4: upload new Takswarrior tasks'.format(project.project_name))
        for taskwarrior_pending_task in self.taskwarrior_client.get_pending_tasks(project.project_name):
            logger.info('Uploading new pending Taskwarrior task with ID {} to Trello'.format(taskwarrior_pending_task['id']))
            if taskwarrior_pending_task.active:
                # Upload new pending active task to doing list
                self.upload_taskwarrior_task(taskwarrior_pending_task, self.trello_client.get_trello_list(project.trello_board_name, trello_lists, project.trello_doing_list))
                taskwarrior_pending_task['trellolistname'] = project.trello_doing_list
                taskwarrior_pending_task.save()
            else:
                if taskwarrior_pending_task['trellolistname']:
                    # Upload new pending task to user provided list
                    self.upload_taskwarrior_task(taskwarrior_pending_task, self.trello_client.get_trello_list(project.trello_board_name, trello_lists, taskwarrior_pending_task['trellolistname']))
                else:
                    # Upload new pending task to default todo list
                    self.upload_taskwarrior_task(taskwarrior_pending_task, self.trello_client.get_trello_list(project.trello_board_name, trello_lists, project.trello_todo_list))
                    taskwarrior_pending_task['trellolistname'] = project.trello_todo_list
                    taskwarrior_pending_task.save()
        for taskwarrior_completed_task in self.taskwarrior_client.get_completed_tasks(project.project_name):
            logger.info('Uploading new completed Taskwarrior task to Trello')
            self.upload_taskwarrior_task(taskwarrior_completed_task, self.trello_client.get_trello_list(project.trello_board_name, trello_lists, project.trello_done_list))
            taskwarrior_completed_task['trellolistname'] = project.trello_done_list
            taskwarrior_completed_task.save()
        logger.info('Project {} synchronized'.format(project.project_name))