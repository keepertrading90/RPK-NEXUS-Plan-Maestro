import math
from typing import List, Dict, Any

class SimulationResult:
    def __init__(self, lead_time_hours: float, max_queue: float, timeline: List[Dict[str, Any]]):
        self.lead_time_hours = lead_time_hours
        self.max_queue = max_queue
        self.timeline = timeline

def simulate_transfer_batch(
    total_lot: int, 
    transfer_batch: int, 
    rate_a: float, 
    rate_c: float
) -> SimulationResult:
    """
    Simula la producción de una máquina C que es alimentada por una Máquina A en lotes de transferencia.
    rate_a: cadencia cabecera (piezas/hora)
    rate_c: cadencia secundaria (piezas/hora)
    """
    if transfer_batch <= 0 or total_lot <= 0 or rate_a <= 0 or rate_c <= 0:
        return SimulationResult(0, 0, [])

    num_batches = math.ceil(total_lot / transfer_batch)
    timeline = []
    
    current_time = 0.0
    queue = 0
    max_queue = 0
    
    # Tracking the time when machine C is free to start the next batch
    c_available_time = 0.0
    
    # We will sample the timeline at every batch completion
    for i in range(num_batches):
        pieces_in_batch = transfer_batch if (i < num_batches - 1) else (total_lot - (i * transfer_batch))
        
        # Machine A finishes this batch
        time_a_finishes_batch = (i + 1) * transfer_batch / rate_a if (i < num_batches - 1) else total_lot / rate_a
        
        # Machine C can start only when it's free AND the batch is ready
        c_starts_batch = max(c_available_time, time_a_finishes_batch)
        
        # The time machine C takes to process this batch
        c_process_time = pieces_in_batch / rate_c
        c_finishes_batch = c_starts_batch + c_process_time
        
        # Queue estimation when C starts
        current_queue = (c_starts_batch * rate_a) - (i * transfer_batch) # Rough estimation of pieces waiting
        if current_queue > max_queue:
            max_queue = current_queue
            
        timeline.append({
            "batch": i + 1,
            "pieces": pieces_in_batch,
            "a_finishes": round(time_a_finishes_batch, 2),
            "c_starts": round(c_starts_batch, 2),
            "c_finishes": round(c_finishes_batch, 2),
            "wait_time_for_c": round(c_starts_batch - time_a_finishes_batch, 2)
        })
        
        c_available_time = c_finishes_batch

    total_lead_time = c_available_time
    
    # If A is significantly faster, the max queue will eventually reach the limit based on the rates
    return SimulationResult(
        lead_time_hours=round(total_lead_time, 2),
        max_queue=round(max_queue, 2),
        timeline=timeline
    )
