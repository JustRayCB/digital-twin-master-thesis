-- Migration 002: Seed default plant

INSERT INTO plants (id, name, notes)
VALUES (
    1,
    'Basil',
    'Basil the 3rd! Doesn''t like being too hot or cold and humidity. He like drinking using the artist entrance.'
)
ON CONFLICT (id) DO NOTHING;
