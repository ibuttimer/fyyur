SET myvars.min_artist_id TO 88;
SET myvars.min_venue_id TO 61;

DELETE FROM public."artist_genres" WHERE artist_id < current_setting('myvars.min_artist_id')::int ;
DELETE FROM public."venue_genres" WHERE venue_id < current_setting('myvars.min_venue_id')::int ;
DELETE FROM public."Shows" WHERE artist_id < current_setting('myvars.min_artist_id')::int or venue_id < current_setting('myvars.min_venue_id')::int ;
DELETE FROM public."Availability" WHERE artist_id < current_setting('myvars.min_artist_id')::int ;
DELETE FROM public."Artist"	WHERE id < current_setting('myvars.min_artist_id')::int ;
DELETE FROM public."Venue" WHERE id < current_setting('myvars.min_venue_id')::int ;