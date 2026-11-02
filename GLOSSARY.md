# Localbini

An app for booking places at local events. Organizers publish events at a specific location and date; visitors find them by location and date and pay to book.

## Language

### People

**Visitor**:
Anyone browsing events, whether logged in or not.
_Avoid_: Guest, customer

**Attendee**:
A logged-in user who holds a Booking for an Event.
_Avoid_: Buyer, customer, participant

**Organizer**:
A user with the organizer role who creates and manages Events.
_Avoid_: Host, publisher

**Admin**:
One of a few named users with the admin role, who run the platform.
_Avoid_: Superuser, operator

### Events

**Event**:
Something that happens at one Location on a specific date and time, with a limited number of places and a price.
_Avoid_: Listing, show, happening

**Event status**:
Where an Event is in its life. A **Draft** is visible only to its Organizer and Admins. A **Published** Event is visible to everyone and open for Booking. A **Cancelled** Event is closed, and its Attendees are notified.
_Avoid_: Active, live, deleted

**Places**:
How many Attendees an Event can hold in total. A Booking takes one or more places.
_Avoid_: Capacity, seats, tickets

**Location**:
The place where an Event happens. Visitors search for Events by Location.
_Avoid_: Venue, address, place

**Cover picture**:
The main image shown for an Event.
_Avoid_: Banner, thumbnail, hero image

**Important information**:
Practical notes an Attendee must know before going, such as the dress code, an age limit or what to bring.
_Avoid_: Notes, details, FAQ

### Booking

**Booking**:
An Attendee's reservation of one or more places at an Event. It is confirmed once payment succeeds.
_Avoid_: Order, reservation, ticket purchase

**Hold**:
Places set aside for a few minutes while an Attendee is in Checkout. If payment doesn't succeed in time, the places are released.
_Avoid_: Lock, reservation, pending booking

**Checkout**:
The step where an Attendee pays for a Booking through Stripe.
_Avoid_: Payment flow, purchase
