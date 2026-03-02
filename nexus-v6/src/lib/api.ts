import type { ApiResponse, HubStats } from '@/types/api-contracts';

const API_BASE = '/api';

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });

    if (!res.ok) {
        throw new Error(`API Error: ${res.status} ${res.statusText}`);
    }

    return res.json();
}

export async function getHubStats(): Promise<HubStats> {
    return fetchApi<HubStats>('/v1/hub_stats');
}

export async function getPedidosSummary() {
    return fetchApi('/pedidos/summary');
}

export async function getPedidosArticulos() {
    return fetchApi('/pedidos/articulos');
}

export async function getAlbaranesResumen(start?: string, end?: string) {
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    const qs = params.toString();
    return fetchApi(`/albaranes/resumen${qs ? '?' + qs : ''}`);
}

export async function getAlbaranesClientes(start?: string, end?: string) {
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    const qs = params.toString();
    return fetchApi(`/albaranes/clientes${qs ? '?' + qs : ''}`);
}

export async function getTiemposSummary() {
    return fetchApi('/tiempos/summary');
}

export async function getStockSummary(start?: string, end?: string) {
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    const qs = params.toString();
    return fetchApi(`/summary${qs ? '?' + qs : ''}`);
}
