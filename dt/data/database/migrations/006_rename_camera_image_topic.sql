-- Migration 006: Renamed legacy camera snapshot topic names

UPDATE camera_snapshots
SET topic = 'camera_image_top'
WHERE topic IN ('camera_image', 'dt.sensors.camera_image');
