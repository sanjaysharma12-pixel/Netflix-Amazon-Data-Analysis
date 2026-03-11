CREATE DATABASE netflix_db;
USE netflix_db;

CREATE TABLE netflix_amazon (
    show_id VARCHAR(20),
    type VARCHAR(20),
    title TEXT,
    director TEXT,
    cast TEXT,
    country TEXT,
    date_added VARCHAR(50),
    release_year INT,
    rating VARCHAR(20),
    duration VARCHAR(50),
    listed_in TEXT,
    description TEXT,
    year_added INT,
    month_added INT
);


LOAD DATA INFILE 'C:/ProgramData/MySQL/MySQL Server 8.0/Uploads/clean_netflix_amazon_dataset (1) (1).csv1'
INTO TABLE netflix_amazon
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

SELECT * FROM netflix_amazon LIMIT 5;

#Content Lifecycle Analysis (Yearly Trend with Type)

SELECT 
    year_added, 
    type, 
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY year_added), 2) AS percentage_share
FROM  netflix_amazon
WHERE year_added IS NOT NULL
GROUP BY year_added, type
ORDER BY year_added DESC;

#Genre-Platform "Heatmap" Analysis

SELECT 
    TRIM(SUBSTRING_INDEX(listed_in, ',', 1)) AS primary_genre,
    type,
    COUNT(*) AS total_content
FROM netflix_amazon
GROUP BY primary_genre, type
HAVING total_content > 50
ORDER BY total_content DESC;

#Rating Diversity Analysis (Target Audience Identification)

SELECT 
    rating, 
    COUNT(*) AS total_content,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM netflix_amazon), 2) AS percentage_share
FROM netflix_amazon
GROUP BY rating
ORDER BY total_content DESC;

#"Binge-Watchability" Index (Duration Analysis)

SELECT 
    type,
    CASE 
        WHEN type = 'Movie' THEN 'Standard'
        WHEN type = 'TV Show' THEN 'High Engagement'
    END AS engagement_potential,
    COUNT(*) AS total_titles
FROM netflix_amazon
GROUP BY type;

#"Release Intensity" (Year-over-Year Growth Rate)
SELECT 
    year_added,
    COUNT(*) AS current_year_count,
    LAG(COUNT(*)) OVER (ORDER BY year_added) AS previous_year_count,
    ROUND(((COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY year_added)) / LAG(COUNT(*)) OVER (ORDER BY year_added)) * 100, 2) AS growth_percentage
FROM netflix_amazon
WHERE year_added IS NOT NULL
GROUP BY year_added;

#Top 10 Genres (Audience Preference)

SELECT listed_in, COUNT(*) AS genre_count
FROM netflix_amazon
GROUP BY listed_in
ORDER BY genre_count DESC
LIMIT 10;

#Top 10 Producing Countries

SELECT country, COUNT(*) AS production_count
FROM netflix_amazon
WHERE country != 'Unknown'
GROUP BY country
ORDER BY production_count DESC
LIMIT 10;

#Rating Analysis (Target Audience)
SELECT rating, COUNT(*) AS total_content
FROM netflix_amazon
GROUP BY rating
ORDER BY total_content DESC;

#Content Gap Analysis
SELECT listed_in, COUNT(*) AS count
FROM netflix_amazon
GROUP BY listed_in
HAVING count < 50
ORDER BY count ASC;

#Year-over-Year Growth Percentage
SELECT year_added, 
       COUNT(*) AS current_count,
       LAG(COUNT(*)) OVER (ORDER BY year_added) AS prev_count,
       ((COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY year_added)) / LAG(COUNT(*)) OVER (ORDER BY year_added)) * 100 AS growth_pct
FROM netflix_amazon
GROUP BY year_added;