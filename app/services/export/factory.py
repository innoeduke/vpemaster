from .base import BaseExportBoard
from .components import (
    AgendaComponent,
    MeetingMasterComponent,
    PowerBIAgendaComponent,
    YoodliLinksComponent,
    RosterComponent,
    ParticipantsComponent,
    VotesComponent,
    SpeechObjectivesComponent,
)


class ExportFactory:
    """Factory to create export boards for a meeting."""
    @staticmethod
    def get_meeting_boards():
        boards = []
        
        # Sheet 1: Agenda
        agenda_board = BaseExportBoard("Agenda")
        agenda_board.add_component(AgendaComponent())
        agenda_board.add_component(SpeechObjectivesComponent())
        boards.append(agenda_board)
        
        # Sheet 2: PowerBI Data
        pbi_board = BaseExportBoard("PowerBI Data")
        pbi_board.add_component(MeetingMasterComponent())
        pbi_board.add_component(PowerBIAgendaComponent())
        pbi_board.add_component(YoodliLinksComponent())
        boards.append(pbi_board)
        
        # Sheet 3: Roster
        roster_board = BaseExportBoard("Roster")
        roster_board.add_component(RosterComponent())
        boards.append(roster_board)
        
        # Sheet 4: Participants
        part_board = BaseExportBoard("Participants")
        part_board.add_component(ParticipantsComponent())
        boards.append(part_board)
        
        # Sheet 5: Votes
        votes_board = BaseExportBoard("Votes")
        votes_board.add_component(VotesComponent())
        boards.append(votes_board)
        
        return boards
