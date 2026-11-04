-- แสดงข้อมูลทุกแถวที่ Python นำเข้ามา
SELECT *
FROM camera_detection_logs
ORDER BY captured_at;

SELECT
    qr_text AS product_code,
    SUM(object_count) AS total_object_count
FROM camera_detection_logs
WHERE qr_text IS NOT NULL
  AND qr_text <> ''
GROUP BY qr_text
ORDER BY product_code;

SELECT
    camera_id,
    SUM(object_count) AS total_object_count,
    COUNT(*) AS total_detection_records
FROM camera_detection_logs
GROUP BY camera_id
ORDER BY camera_id;

SELECT *
FROM camera_detection_logs
WHERE qr_text IS NULL
   OR qr_text = '';