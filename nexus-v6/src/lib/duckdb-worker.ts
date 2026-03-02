/**
 * DuckDB WASM Worker — Singleton para queries SQL en el navegador.
 * 
 * Uso:
 *   const db = useDuckDB();
 *   const result = await db.query("SELECT * FROM stock WHERE cantidad > 100");
 * 
 * El worker descarga los .parquet del backend y los registra como tablas SQL.
 * Las queries se ejecutan localmente → latencia sub-milisegundo.
 */

import * as duckdb from '@duckdb/duckdb-wasm';

let dbInstance: duckdb.AsyncDuckDB | null = null;
let connInstance: duckdb.AsyncDuckDBConnection | null = null;
let initPromise: Promise<void> | null = null;

const PARQUET_TABLES: Record<string, string> = {
    existencias: '/api/parquet/existencias',
    pedidos: '/api/parquet/pedidos',
    albaranes: '/api/parquet/albaranes',
    carga_centros: '/api/parquet/carga_centros',
    carga_detalle: '/api/parquet/carga_detalle',
};

async function initDB(): Promise<void> {
    if (dbInstance) return;

    // CDN bundles for DuckDB WASM
    const DUCKDB_BUNDLES = await duckdb.selectBundle({
        mvp: {
            mainModule: new URL('@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm', import.meta.url).href,
            mainWorker: new URL('@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js', import.meta.url).href,
        },
        eh: {
            mainModule: new URL('@duckdb/duckdb-wasm/dist/duckdb-eh.wasm', import.meta.url).href,
            mainWorker: new URL('@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js', import.meta.url).href,
        },
    });

    const logger = new duckdb.ConsoleLogger();
    const worker = new Worker(DUCKDB_BUNDLES.mainWorker!);
    dbInstance = new duckdb.AsyncDuckDB(logger, worker);
    await dbInstance.instantiate(DUCKDB_BUNDLES.mainModule);
    connInstance = await dbInstance.connect();

    console.log('[DuckDB WASM] Motor SQL inicializado en el navegador');
}

/**
 * Registra un archivo .parquet como tabla en DuckDB WASM.
 */
async function registerParquetTable(tableName: string, url: string): Promise<void> {
    if (!dbInstance || !connInstance) throw new Error('DuckDB no inicializado');

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status} al descargar ${url}`);
        const buffer = await response.arrayBuffer();

        await dbInstance.registerFileBuffer(`${tableName}.parquet`, new Uint8Array(buffer));
        await connInstance.query(`
      CREATE OR REPLACE TABLE ${tableName} AS 
      SELECT * FROM read_parquet('${tableName}.parquet')
    `);

        console.log(`[DuckDB WASM] Tabla '${tableName}' registrada (${(buffer.byteLength / 1024).toFixed(0)} KB)`);
    } catch (err) {
        console.warn(`[DuckDB WASM] No se pudo cargar '${tableName}': ${err}`);
    }
}

/**
 * Ejecuta una query SQL y devuelve los resultados como array de objetos.
 */
async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
    if (!connInstance) throw new Error('DuckDB no conectado');

    const result = await connInstance.query(sql);
    const rows: T[] = [];
    const numRows = result.numRows;
    const schema = result.schema.fields;

    for (let i = 0; i < numRows; i++) {
        const row: Record<string, unknown> = {};
        for (const field of schema) {
            const col = result.getChildAt(schema.indexOf(field));
            row[field.name] = col?.get(i);
        }
        rows.push(row as T);
    }

    return rows;
}

/**
 * Carga todas las tablas del Data Lakehouse en DuckDB WASM.
 */
async function loadAllTables(): Promise<string[]> {
    const loaded: string[] = [];
    for (const [name, url] of Object.entries(PARQUET_TABLES)) {
        try {
            await registerParquetTable(name, url);
            loaded.push(name);
        } catch {
            // Graceful Degradation - seguir con las tablas que sí se carguen
        }
    }
    return loaded;
}

// Hook de React para acceder a DuckDB WASM
export function useDuckDBInit() {
    if (!initPromise) {
        initPromise = initDB();
    }
    return {
        init: () => initPromise,
        loadAllTables,
        query,
        registerParquetTable,
    };
}

export { initDB, query, loadAllTables, registerParquetTable };
