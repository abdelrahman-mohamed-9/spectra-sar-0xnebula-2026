from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from spectra.persistence.models import Base

EXPECTED = {'projects','areas_of_interest','sar_scenes','artifacts','scene_pairs',
            'processing_jobs','change_results','impact_assessments','audit_events','users','project_memberships'}


def test_tables_and_keys():
    assert set(Base.metadata.tables) == EXPECTED
    for table in Base.metadata.tables.values():
        assert ('id' in table.primary_key.columns or table.name == 'project_memberships')


def test_ddl_compiles_for_postgres():
    d = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=d))
        assert 'CREATE TABLE' in ddl
        for index in table.indexes:
            assert 'CREATE INDEX' in str(CreateIndex(index).compile(dialect=d))


def test_geospatial_fields_and_indexes():
    for table, column in [('areas_of_interest','geometry'),('sar_scenes','footprint'),
                          ('impact_assessments','affected_area')]:
        col = Base.metadata.tables[table].c[column]
        assert col.type.get_col_spec() == 'geometry(MULTIPOLYGON,4326)'
        assert any(column in i.columns and i.dialect_options['postgresql']['using'] == 'gist'
                   for i in Base.metadata.tables[table].indexes)


def test_expected_foreign_keys():
    references = {(table.name, fk.parent.name, fk.column.table.name)
                  for table in Base.metadata.tables.values() for fk in table.foreign_keys}
    assert ('change_results','scene_pair_id','scene_pairs') in references
    assert ('impact_assessments','change_result_id','change_results') in references
    assert ('scene_pairs','aoi_id','areas_of_interest') in references
