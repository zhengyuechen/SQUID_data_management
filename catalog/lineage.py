"""Lineage queries — the product_input link is traversable both directions."""

def raws_of_product(conn, product_id):
    return [dict(r) for r in conn.execute(
        """SELECT r.*, pi.role FROM raw_measurement r JOIN product_input pi ON pi.raw_measurement_id=r.id
           WHERE pi.derived_product_id=? ORDER BY r.temp_mK, r.run_index""", (product_id,))]

def products_of_raw(conn, raw_id):
    return [dict(r) for r in conn.execute(
        """SELECT d.*, pi.role FROM derived_product d JOIN product_input pi ON pi.derived_product_id=d.id
           WHERE pi.raw_measurement_id=? ORDER BY d.created_at""", (raw_id,))]
