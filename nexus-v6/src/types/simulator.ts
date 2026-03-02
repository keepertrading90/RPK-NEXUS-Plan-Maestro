export interface SimulatorOverride {
    articulo: string;
    centro: string;
    field: string;
    original: number;
    value: number;
    label?: string;
}

export interface CenterConfig {
    shifts: number;
    personnel_ratio: number;
}

export interface ScenarioMeta {
    id: string | number;
    name: string;
    created_at?: string;
}

export interface CentroRow {
    centro: string;
    centro_label?: string;
    capacidad_h: number;
    carga_h: number;
    setup_h: number;
    saturacion: number;
    articulos: ArticuloRow[];
}

export interface ArticuloRow {
    articulo: string;
    descripcion?: string;
    centro: string;
    demanda: number;
    cadencia: number;
    oee: number;
    ppm: number;
    carga_h: number;
    setup_h: number;
    setup_min?: number;
    traslado?: number;
}

export interface SimulationData {
    centros: CentroRow[];
    summary: {
        total_carga_h: number;
        total_setup_h: number;
        total_capacidad_h: number;
        saturacion_media: number;
    };
}

export interface ComparisonResult {
    centros: {
        centro: string;
        saturacion_a: number;
        saturacion_b: number;
        delta: number;
        carga_h_a: number;
        carga_h_b: number;
    }[];
}
