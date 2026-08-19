CREATE TABLE materials(
    material_id TEXT PRIMARY KEY,
    formula_pretty TEXT,
    crystal_system TEXT,
    spacegroup_symbol TEXT,
    spacegroup_number INTEGER,
    volume FLOAT,
    nsites INTEGER,
    nelements INTEGER,
    is_stable BOOLEAN,
    energy_above_hull FLOAT,
    s3_key TEXT,
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE properties(

    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    property_name TEXT NOT NULL,
    value FLOAT,
    unit TEXT,
    functional TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (material_id, property_name),
    FOREIGN KEY (material_id)
    REFERENCES materials(material_id)
);

CREATE TABLE material_elements(
    material_id TEXT NOT NULL,
    element_symbol TEXT,
    atomic_fraction FLOAT,
    PRIMARY KEY (material_id, element_symbol),
    FOREIGN KEY(material_id)
    REFERENCES materials(material_id)
);

CREATE INDEX idx_properties_material_id ON properties(material_id);
CREATE INDEX idx_properties_property_name ON properties(property_name);