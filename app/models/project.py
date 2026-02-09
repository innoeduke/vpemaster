"""Project and pathway models."""
from .base import db
from ..constants import ProjectID


class Project(db.Model):
    __tablename__ = 'Projects'
    id = db.Column(db.Integer, primary_key=True)
    Project_Name = db.Column(db.String(255), nullable=False)
    Format = db.Column(db.String(50))
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    Introduction = db.Column(db.String(1000))
    Overview = db.Column(db.String(1000))
    Purpose = db.Column(db.String(255))
    Requirements = db.Column(db.String(500))
    Resources = db.Column(db.String(500))
    
    @property
    def is_generic(self):
        """Returns True if this is the generic project."""
        return self.id == ProjectID.GENERIC

    @property
    def is_presentation(self):
        """Returns True if this is a presentation project."""
        return self.Format == 'Presentation'

    @property
    def is_prepared_speech(self):
        """Returns True if this is a prepared speech project."""
        return self.Format == 'Prepared Speech'

    def resolve_context(self, context_path_name=None):
        """
        Helper to find the best matching PathwayProject entry and its Pathway.
        Returns tuple (PathwayProject, Pathway).
        """
        pp = None
        path_obj = None
        
        if context_path_name:
        # Try finding by name first, then by abbreviation
            path_obj = db.session.query(Pathway).filter(
                (Pathway.name == context_path_name) | (Pathway.abbr == context_path_name)
            ).first()
        
            if path_obj:
                pp = db.session.query(PathwayProject).filter_by(
                    path_id=path_obj.id, project_id=self.id).first()
                if not pp:
                    path_obj = None # Reset if project not found in this path

        # Fallback: Check if it belongs to ANY pathway
        if not pp:
            pp = db.session.query(PathwayProject).filter_by(project_id=self.id).first()
            if pp:
                path_obj = db.session.get(Pathway, pp.path_id)
        
        return pp, path_obj
    
    @classmethod
    def prefetch_context(cls, project_ids):
        """
        Pre-fetch PathwayProject data for a list of project IDs to avoid N+1 queries.
        Returns a cache dictionary: {project_id: [{'pp': PathwayProject, 'path': Pathway}, ...]}
        """
        if not project_ids:
            return {}

        pp_entries = db.session.query(PathwayProject, Pathway)\
            .join(Pathway, PathwayProject.path_id == Pathway.id)\
            .filter(PathwayProject.project_id.in_(project_ids))\
            .all()
            
        pp_cache = {}
        for pp, path in pp_entries:
            if pp.project_id not in pp_cache:
                pp_cache[pp.project_id] = []
            pp_cache[pp.project_id].append({'pp': pp, 'path': path})
        return pp_cache

    @classmethod
    def resolve_context_from_cache(cls, project_id, context_path_name, cache):
        """
        Resolve context (PathwayProject, Pathway) using the pre-fetched cache.
        """
        if not project_id or project_id not in cache:
            return None, None
            
        entries = cache[project_id]
        match = None
        
        # 1. Try exact match by name or abbr
        if context_path_name:
            for entry in entries:
                if entry['path'].name == context_path_name or entry['path'].abbr == context_path_name:
                    match = entry
                    break
        
        # 2. Fallback: Take first available if no match found
        if not match and entries:
            match = entries[0]
            
        if match:
            return match['pp'], match['path']
        return None, None

    def get_code(self, context_path_name=None):
        """
        Returns the project code based on a pathway context.
        """
        # Handle generic project
        if self.is_generic:
            return "TM1.0"

        if self.is_presentation:
            context_path_name = None

        pp, path_obj = self.resolve_context(context_path_name)

        if pp:
            if path_obj and path_obj.abbr:
                return f"{path_obj.abbr}{pp.code}"
            else:
                return pp.code

        return ""

    def get_level(self, context_path_name=None):
        """
        Returns the level based on a pathway context.
        """
        if self.is_generic:
            return 1
            
        if self.is_presentation:
            context_path_name = None
            
        pp, _ = self.resolve_context(context_path_name)
        if pp and pp.level:
            return pp.level
            
        return 1


class Pathway(db.Model):
    __tablename__ = 'pathways'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    abbr = db.Column(db.String(5))
    type = db.Column(db.String(20))
    status = db.Column(db.Enum('active', 'inactive', 'obsolete', name='pathway_status_enum'), default='active', nullable=False)


class PathwayProject(db.Model):
    __tablename__ = 'pathway_projects'
    id = db.Column(db.Integer, primary_key=True)
    path_id = db.Column(db.Integer, db.ForeignKey('pathways.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('Projects.id'))
    code = db.Column(db.String(10))
    level = db.Column(db.Integer, nullable=True)
    type = db.Column(db.Enum('elective', 'required', 'other', name='pathway_project_type_enum'), nullable=False)

    pathway = db.relationship('Pathway', backref='pathway_projects')
    project = db.relationship('Project', backref='pathway_projects')


class LevelRole(db.Model):
    __tablename__ = 'level_roles'
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    count_required = db.Column(db.Integer, nullable=False, default=0)
    band = db.Column(db.Integer, nullable=True)
