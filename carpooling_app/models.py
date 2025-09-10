from django.db import models

class Person(models.Model):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=15, unique=True)
    first_name = models.CharField(max_length=15)
    last_name = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(max_length=50,unique=True)
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=12, unique=True)
    profile_pic = models.ImageField(upload_to="profiles/", null=True, blank=True )
    role = models.CharField(max_length=20, choices=[("admin", "Admin"), ("driver", "Driver"), ("passenger", "Passenger")], default="passenger")
    is_active = models.BooleanField(default=False)
    address = models.TextField(null=True, blank=True)

    REQUIRED_FIELDS = ['username', 'first_name', 'email', 'password']

    def __str__(self):
        return self.username


# Journey / Create Car Pool
class CreateCarpool(models.Model):
    createcarpool_id = models.AutoField(primary_key=True)
    carpool_creator_driver = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="journeys")
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField(null=True, blank=True)
    available_seats = models.IntegerField()
    contribution_per_passenger = models.DecimalField(max_digits=10, decimal_places=2)
    add_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total_passenger_allowed = models.PositiveIntegerField()
    contact_info = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.carpool_creator_driver.username


# Booking (Passenger joins Journey)
class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    fkCreateCarpool = models.ForeignKey(CreateCarpool, on_delete=models.CASCADE, related_name="bookings")
    passenger_name = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="passenger_bookings")
    seat_book = models.PositiveIntegerField(default=1)
    contribution_amount = models.DecimalField(max_digits=10, decimal_places=2)
    booking_status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")], default="pending")
    booked_by = models.ForeignKey(Person, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)
    pickup_location = models.CharField(max_length=255, null=True, blank=True)
    drop_location = models.CharField(max_length=255, null=True, blank=True)


    def __str__(self):
        return self.booking_id
    
## Model for activity log (Foreignkey used -->> User)
class Activity(models.Model):
    date_time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(Person, on_delete=models.SET_NULL,null=True, blank=True)
    details = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.user}----{self.date_time}----{self.Details}'


class Transaction(models.Model):
    transaction_id = models.AutoField(primary_key=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="transaction")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20,choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")],default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Person, on_delete=models.CASCADE)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.payment_status}"