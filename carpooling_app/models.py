from django.db import models

## User Model
class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=15, unique=True)
    first_name = models.CharField(max_length=15)
    last_name = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=12, unique=True)
    profile_pic = models.ImageField(upload_to="profiles/", null=True, blank=True)
    role = models.CharField(max_length=20, choices=[("admin", "Admin"), ("driver", "Driver"), ("passenger", "Passenger")], default="passenger")
    is_active = models.BooleanField(default=False)
    address = models.TextField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female"), ("other", "Other")], null=True, blank=True)

    def __str__(self):
        return f"{self.user_id} ({self.username})"

## Carpool Model
class CreateCarpool(models.Model):
    createcarpool_id = models.AutoField(primary_key=True)
    carpool_creator_driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="journeys")
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField(null=True, blank=True)
    available_seats = models.IntegerField()
    total_passenger_allowed = models.PositiveIntegerField()
    contribution_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=0) 
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=0) 
    add_note = models.TextField(blank=True, null=True)
    allow_luggage = models.BooleanField(default=True)
    gender_preference = models.CharField(max_length=10, choices=[("any", "Any"),("male", "Male"),("female", "Female")], default="any")
    contact_info = models.TextField(null=True, blank=True)
    car_model = models.CharField(max_length=50, null=True, blank=True) 
    car_number = models.CharField(max_length=20, null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="updated_carpool")
    ## MySQL latitude & longitude fields
    latitude_start = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude_start = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    latitude_end = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude_end = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return self.carpool_creator_driver.username

## Booking Model
class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    carpool_driver_name = models.ForeignKey(CreateCarpool, on_delete=models.CASCADE, related_name="bookings")
    passenger_name = models.ForeignKey(User, on_delete=models.CASCADE, related_name="passenger_bookings")
    seat_book = models.PositiveIntegerField(default=1)
    # distance_travelled = models.PositiveIntegerField(null=True, blank=True, help_text="Distance passenger will travel (in km)")
    distance_travelled = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contribution_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_mode = models.CharField(max_length=10, choices=[("cash", "Cash"), ("upi", "UPI")], default="cash")
    booking_status = models.CharField(max_length=20,choices=[("pending", "Pending"),("confirmed", "Confirmed"),("rejected", "Rejected"),("cancelled", "Cancelled"),
                                                             ("waitlisted", "Waitlisted"),],default="pending")
    ride_status = models.CharField(max_length=20, choices=[("upcoming", "Upcoming"), ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="upcoming")
    booked_by = models.ForeignKey(User, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)
    pickup_location = models.CharField(max_length=255, null=True, blank=True)
    drop_location = models.CharField(max_length=255, null=True, blank=True)
    contact_info = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="updated_booking")

    def __str__(self):
        return self.passenger_name.username

## Contact Us (Visitors)
class Contact(models.Model):
    contact_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    email = models.EmailField()
    phone_number = models.CharField(max_length=12, unique=True)
    your_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.email}"

## Activity Logs
class Activity(models.Model):
    date_time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.user}----{self.date_time}----{self.details}'

## Review and Rating
class ReviewRating(models.Model):
    review_id = models.AutoField(primary_key=True)
    review_given_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_reviews")  
    review_for = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_reviews")  
    carpool_driver = models.ForeignKey(CreateCarpool, on_delete=models.CASCADE, related_name="reviews")
    booking_person_name = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveIntegerField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.review_given_by.username} → {self.review_for.username} ({self.rating})"
