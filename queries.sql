-- OLA Ride Insights: SQL queries (SQLite dialect; table `rides` is created by clean_data.py)
-- Each block starts with "-- Q<n>: <title>" so the Streamlit app can load and run it.

-- Q1: Retrieve all successful bookings
SELECT *
FROM rides
WHERE booking_status = 'Success';

-- Q2: Average ride distance for each vehicle type
-- avg_distance_all_bookings includes cancelled rides (distance 0) and matches the reference sheet;
-- avg_distance_completed covers successful bookings only.
SELECT vehicle_type,
       ROUND(AVG(ride_distance), 2) AS avg_distance_all_bookings,
       ROUND(AVG(CASE WHEN booking_status = 'Success' THEN ride_distance END), 2) AS avg_distance_completed
FROM rides
GROUP BY vehicle_type
ORDER BY avg_distance_completed DESC;

-- Q3: Total number of rides cancelled by customers
SELECT COUNT(*) AS cancelled_by_customers
FROM rides
WHERE booking_status = 'Canceled by Customer';

-- Q4: Top 5 customers by number of rides booked (ties broken by total booking value)
SELECT customer_id,
       COUNT(*) AS total_rides,
       SUM(booking_value) AS total_booking_value
FROM rides
GROUP BY customer_id
ORDER BY total_rides DESC, total_booking_value DESC, customer_id
LIMIT 5;

-- Q5: Rides cancelled by drivers for personal and car related issues
SELECT COUNT(*) AS driver_cancellations_personal_car
FROM rides
WHERE cancel_reason_driver = 'Personal & Car related issue';

-- Q6: Maximum and minimum driver ratings for Prime Sedan bookings
SELECT MAX(driver_rating) AS max_driver_rating,
       MIN(driver_rating) AS min_driver_rating
FROM rides
WHERE vehicle_type = 'Prime Sedan';

-- Q7: All rides paid with UPI
SELECT *
FROM rides
WHERE payment_method = 'UPI';

-- Q8: Average customer rating per vehicle type
SELECT vehicle_type,
       ROUND(AVG(customer_rating), 2) AS avg_customer_rating
FROM rides
GROUP BY vehicle_type
ORDER BY avg_customer_rating DESC;

-- Q9: Total booking value of successfully completed rides
SELECT SUM(booking_value) AS total_booking_value
FROM rides
WHERE booking_status = 'Success';

-- Q10: All incomplete rides with the reason
SELECT booking_id, booking_date, vehicle_type, pickup_location, drop_location,
       incomplete_reason
FROM rides
WHERE incomplete_ride = 'Yes'
ORDER BY booking_date;

-- Q11: Demand by hour of day (supports the peak-hours use case)
SELECT hour,
       COUNT(*) AS bookings,
       SUM(CASE WHEN booking_status = 'Success' THEN 1 ELSE 0 END) AS successful
FROM rides
GROUP BY hour
ORDER BY hour;

-- Q12: Cancellation and driver-not-found rate by vehicle type
SELECT vehicle_type,
       COUNT(*) AS bookings,
       ROUND(100.0 * SUM(booking_status = 'Canceled by Customer') / COUNT(*), 2) AS customer_cancel_pct,
       ROUND(100.0 * SUM(booking_status = 'Canceled by Driver') / COUNT(*), 2) AS driver_cancel_pct,
       ROUND(100.0 * SUM(booking_status = 'Driver Not Found') / COUNT(*), 2) AS no_driver_pct
FROM rides
GROUP BY vehicle_type
ORDER BY bookings DESC;

-- Q13: Revenue by payment method (completed rides)
SELECT payment_method,
       COUNT(*) AS rides,
       SUM(booking_value) AS revenue
FROM rides
WHERE booking_status = 'Success'
GROUP BY payment_method
ORDER BY revenue DESC;
