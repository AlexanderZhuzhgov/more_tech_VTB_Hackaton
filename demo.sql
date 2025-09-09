select f.flight_id
		,f.flight_no 
		,EXTRACT(MONTH FROM f.scheduled_departure)		as month_scheduled_departure
		,date(f.scheduled_departure)					as date_scheduled_departure
		,f.scheduled_departure 		
		,EXTRACT(MONTH FROM f.scheduled_arrival)		as month_scheduled_arrival
		,date(f.scheduled_arrival)						as date_scheduled_arrival
		,f.scheduled_arrival 
		,f.departure_airport 
		,f.arrival_airport 
		,f.status 
		,f.aircraft_code 
		,f.actual_departure 
		,f.actual_arrival 
		,ad.model ->> 'en' AS model_en
		,ad."range"
from bookings.flights f 
	inner join bookings.ticket_flights t on f.flight_id=t.flight_id 
														and t.amount>50000
	left join bookings.aircrafts_data ad on f.aircraft_code=ad.aircraft_code														
where 1=1 
	and f.departure_airport!='DME'
	and f.arrival_airport ='SVO'
	and f.status!='Arrived'
group by 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16