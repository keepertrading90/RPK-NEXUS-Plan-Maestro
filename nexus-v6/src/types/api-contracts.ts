export interface ApiResponse<T> {
    status: "success" | "error";
    data?: T;
    message?: string;
    error?: string;
    warning?: string;
}

// === MODELS ===

export interface HubStats {
    stock: {
        total: number;
    };
    saturation: string;
    cobertura: string;
}

export interface KpiSummary {
    kpis: {
        total_importe?: number;
        total_piezas?: number;
        num_referencias?: number;
        total_albaranes?: number;
        total_kg?: number;
        num_clientes?: number;
        total_carga_h?: number;
        total_setup_h?: number;
        media_oee?: number;
        saturacion_general?: number;
    };
    ultima_fecha: string;
}

export interface ChartDataEvolucion {
    fechas: string[];
    importes?: number[];
    cantidad?: number[];
    pesos?: number[];
}

export interface BaseResponseWithKpis extends KpiSummary {
    evolucion?: ChartDataEvolucion;
}

export interface TopCliente {
    cliente: string;
    cantidad?: number;
    importe?: number;
}

export interface TopArticulo {
    articulo: string;
    referencia: string;
    cantidad: number;
    importe: number;
}

// Simulador
export interface SimuladorCenterConfig {
    shifts: number;
    personnel_ratio: number;
}

export interface SimuladorOverride {
    articulo?: string;
    centro?: string;
    field: string;
    value: number;
}

export interface SimuladorScenario {
    id?: string | number;
    name: string;
    created_at?: string;
    is_base?: boolean;
}
