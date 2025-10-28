import config as cfg


def compute_objective(served_requests, total_energy):
    """
    Weighted objective blending passenger time (arrival→destination arrival) and energy.
    以乘客全程时间与能耗的加权和作为目标。
    """
    total_passenger_time = 0.0
    total_wait_time = 0.0
    total_in_cab_time = 0.0
    served_count = 0

    for req in served_requests:
        arr = getattr(req, "arrival_time", None)
        origin_arrival = getattr(req, "origin_arrival_time", None)
        dest_arrival = getattr(req, "destination_arrival_time", None)

        if arr is None or dest_arrival is None:
            continue

        served_count += 1

        total_passenger_time += max(dest_arrival - arr, 0.0)

        if origin_arrival is not None:
            wait = max(origin_arrival - arr, 0.0)
            total_wait_time += wait
            total_in_cab_time += max(dest_arrival - origin_arrival, 0.0)
        else:
            # 无 origin_arrival 记录时，将全程记为乘坐时间
            total_in_cab_time += max(dest_arrival - arr, 0.0)

    total_cost = cfg.WEIGHT_TIME * total_passenger_time + cfg.WEIGHT_ENERGY * total_energy

    return (
        total_cost,
        total_passenger_time,
        total_wait_time,
        total_in_cab_time,
        served_count,
    )
