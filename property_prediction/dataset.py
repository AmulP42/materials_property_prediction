import typer
from pathlib import Path
from dotenv import dotenv_values
from loguru import logger
from tqdm import tqdm
from property_prediction.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from mp_api.client import MPRester
import psycopg2 as psy
from psycopg2.extras import execute_values
import boto3
from datetime import datetime
import json
ROOT = Path(__file__).resolve().parents[1]
fields = [
    "material_id",
    "formula_pretty",
    "symmetry",
    "volume",
    "nsites",
    "nelements",
    "is_stable",
    "energy_above_hull",
    "deprecated",
    "composition",
    "band_gap",
    "is_gap_direct",
    "formation_energy_per_atom",
    "bulk_modulus",
    "warnings",
    "structure",
]

def load_config():
    """
    Load environment variables from .env file

    Returns:
        config: ordered dictionary
            dictionary with environemnt variables
    """

    config = dotenv_values(ROOT / ".env")
    return config

def get_mp_client(config):
    """
    Initializes the MPRester client from the MP API key.

    Returns:
        mpr: MPRester object
            initalized MPRester client with API key
    """
    mp_api_key = config["MP_API_KEY"]

    mpr = MPRester(mp_api_key)        
    return mpr

def get_db_connection(config):
    """
    Creates SQLAlchemy engine given DB credentials
    Parameters:
        config: dict
            Dictionary of environment variables
    Returns:
        conn: psycopg2 connection to PostgreSQL database
            Connection to PostgreSQL database url
    """
    conn = psy.connect(
        database = config['DB_NAME'],
        host = config['DB_HOST'],
        user = config['DB_USER'],
        password = config['DB_PASSWORD'],
        port = config['DB_PORT'],
    )
    return conn
    

def get_s3_client():
    """
    Generates boto3 instantiated s3 client

    Returns:
        client: s3 client
            boto3 instantiated s3 client
    """
    client = boto3.client('s3')
    return client

def fetch_all(batch_size, fields, config):
    """
    Fetches data for materials using the mpr client.

    Parameters:
        batch_size: int
            Number of data entries to process per chunk
        fields: list[str]
            List of material fields to extract
        config: dict
            Dictionary of environment variables

    Returns:
        docs: List[SummaryDoc]
            List of SummaryDoc documents
    """

    client = get_mp_client(config)
    docs = client.materials.summary.search(
        fields=fields,
        chunk_size=batch_size,
    )
    return docs

def upload_to_s3(records, batch_num, config):
    """
    Takes a batch of materials and uploads it to the s3 bucket.
    
    Parameters:
        batch: list[SummaryDoc]
            Batch of SummaryDoc documents
        batch_num: int
            Index of current batch
        config: dict
            Dictionary of environment variables
    """
    s3_client = get_s3_client()
    serialized = []
    for record in records:
        d = record.model_dump()
        d['structure'] = record.structure.as_dict() if record.structure else None
        serialized.append(d)
    s3_client.put_object(
        Bucket = config['S3_BUCKET_NAME'],
        Key = f'raw/materials/batch_{batch_num}.json',
        Body = json.dumps(serialized, default=str)
    )

def upsert_materials(conn, records, batch_num):
    """
    Upserts a batch of materials into the materials PostgreSQL DB

    Parameters:
        conn: Pscyopg2 SQL connection
            Connection to PostgreSQL database
        records: list[SummaryDoc]
            List of SummaryDocs to be upserted into DB
        batch_num: int
            Index of batch being inserted
        config: dict
            Dictionary of environment variables


    """
    cur = conn.cursor()
    sql = """
            INSERT INTO materials (material_id, formula_pretty, crystal_system, spacegroup_symbol, spacegroup_number, volume, nsites, nelements, is_stable, energy_above_hull, s3_key, ingested_at)
            VALUES %s 
            ON CONFLICT (material_id) DO UPDATE SET 
                formula_pretty = EXCLUDED.formula_pretty,
                crystal_system = EXCLUDED.crystal_system,
                spacegroup_symbol = EXCLUDED.spacegroup_symbol,
                spacegroup_number = EXCLUDED.spacegroup_number,
                volume = EXCLUDED.volume,
                nsites = EXCLUDED.nsites,
                nelements = EXCLUDED.nelements,
                is_stable = EXCLUDED.is_stable,
                energy_above_hull = EXCLUDED.energy_above_hull,
                s3_key = EXCLUDED.s3_key 
    """
    data = [
        (str(record.material_id), record.formula_pretty, record.symmetry.crystal_system.value, record.symmetry.symbol, record.symmetry.number, record.volume, record.nsites, record.nelements, record.is_stable, record.energy_above_hull, f'raw/materials/batch_{batch_num}.json', datetime.now())
        for record in records
    ]
    execute_values(cur, sql, data)
    conn.commit()

    cur.close()

def upsert_elements(conn, records):
    """
    Upserts a batch of materials into the material_elements PostgreSQL DB

    Parameters:
        conn: Pscyopg2 SQL connection
            Connection to PostgreSQL database
        records: list[SummaryDoc]
            List of SummaryDocs to be upserted into DB
        batch_num: int
            Index of batch being inserted
        config: dict
            Dictionary of environment variables
    """
    cur = conn.cursor()
    sql = """
            INSERT INTO material_elements (material_id, element_symbol, atomic_fraction)
            VALUES %s 
            ON CONFLICT (material_id, element_symbol) DO UPDATE SET 
                element_symbol = EXCLUDED.element_symbol,
                atomic_fraction = EXCLUDED.atomic_fraction
    """
    data = [
        (str(record.material_id), element, fraction / sum(record.composition.as_dict().values())) for record in records for element, fraction in record.composition.as_dict().items()
    ]
    execute_values(cur, sql, data)
    conn.commit()

    cur.close()

def upsert_properties(conn, records):
    """
    Upserts a batch of materials into the properties PostgreSQL DB

    Parameters:
        conn: Pscyopg2 SQL connection
            Connection to PostgreSQL database
        records: list[SummaryDoc]
            List of SummaryDocs to be upserted into DB
        batch_num: int
            Index of batch being inserted
        config: dict
            Dictionary of environment variables
    """
    cur = conn.cursor()
    sql = """
            INSERT INTO properties (material_id, property_name, value, unit, functional, source, created_at)
            VALUES %s 
            ON CONFLICT (material_id, property_name) DO UPDATE SET 
                value = EXCLUDED.value,
                unit = EXCLUDED.unit,
                functional = EXCLUDED.functional,
                source = EXCLUDED.source,
                created_at = EXCLUDED.created_at
    """
    property_names = ["band_gap", "formation_energy_per_atom", "bulk_modulus"]
    name_to_unit = {
        "band_gap": "eV",
        "formation_energy_per_atom": "eV/atom",
        "bulk_modulus": "GPa"
    }
    data = [
        (str(record.material_id), name, getattr(record, name) if name != "bulk_modulus" else (record.bulk_modulus.get("vrh") if record.bulk_modulus else None), name_to_unit[name], "PBE", "materials_project", datetime.now()) for record in records for name in property_names
    ]
    execute_values(cur, sql, data)
    conn.commit()

    cur.close()

def run_ingestion(batch_size=1000):
    # Fetch all materials
    config = load_config()
    try:
        all_materials = fetch_all(1000, fields, config)
    except Exception as e:
        logger.error(f"Failed to fetch materials with error: {e}")
        return
    logger.info("Successfully fetched all materials")

    # Create connection to PostgreSQL DB
    try:
        conn = get_db_connection(config)
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL DB with error: {e}")
        return
    logger.info("Connection to PostgreSQL DB successful")

    # In batches of 1000, creates a subset of records and upserts into the 3 PostgreSQL DBs
    batch_num = 1
    for i in tqdm(range(0, len(all_materials), batch_size), desc="Ingesting batches"):
        records = all_materials[i : min(len(all_materials), i + 1000)]
        upload_to_s3(records, batch_num, config)
        upsert_materials(conn, records, batch_num)
        upsert_elements(conn, records)
        upsert_properties(conn, records)
        batch_num += 1
        logger.info(f"Batch {batch_num} / {len(all_materials)//1000} complete")
    logger.info("Successfully populated database")


    conn.close()


app = typer.Typer()
@app.command()
def main():
    run_ingestion()

if __name__ == "__main__":
    app()
