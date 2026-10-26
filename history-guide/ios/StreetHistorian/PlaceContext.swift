import CoreLocation
import MapKit

/// Everything the guide gets told about where the user is standing.
struct PlaceContext: Codable {
    struct NearbyPlace: Codable {
        let name: String
        let category: String?
        let distanceM: Double
        let bearing: Double
    }

    let latitude: Double
    let longitude: Double
    let horizontalAccuracy: Double
    let heading: Double?
    var address: String?
    var locality: String?
    var administrativeArea: String?
    var country: String?
    var countryCode: String?
    var timeZone: String?
    var nearby: [NearbyPlace] = []
}

enum PlaceContextBuilder {
    /// Reverse-geocodes the position and looks up named points of interest around it,
    /// with each one's distance and compass bearing so the guide can match it to the heading.
    static func build(location: CLLocation, heading: CLLocationDirection?) async -> PlaceContext {
        var context = PlaceContext(
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            horizontalAccuracy: location.horizontalAccuracy,
            heading: heading
        )

        async let placemarks = try? CLGeocoder().reverseGeocodeLocation(location)
        async let pois = nearbyPlaces(around: location)

        if let placemark = await placemarks?.first {
            context.address = [placemark.subThoroughfare, placemark.thoroughfare]
                .compactMap { $0 }
                .joined(separator: " ")
                .nilIfEmpty
            context.locality = placemark.locality
            context.administrativeArea = placemark.administrativeArea
            context.country = placemark.country
            context.countryCode = placemark.isoCountryCode
            context.timeZone = placemark.timeZone?.identifier
        }
        context.nearby = await pois
        return context
    }

    private static func nearbyPlaces(around location: CLLocation) async -> [PlaceContext.NearbyPlace] {
        let request = MKLocalPointsOfInterestRequest(center: location.coordinate, radius: 250)
        guard let response = try? await MKLocalSearch(request: request).start() else { return [] }

        return response.mapItems
            .compactMap { item -> PlaceContext.NearbyPlace? in
                guard let name = item.name else { return nil }
                let coordinate = item.placemark.coordinate
                let target = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
                return PlaceContext.NearbyPlace(
                    name: name,
                    category: item.pointOfInterestCategory?.rawValue,
                    distanceM: location.distance(from: target),
                    bearing: bearing(from: location.coordinate, to: coordinate)
                )
            }
            .sorted { $0.distanceM < $1.distanceM }
            .prefix(20)
            .map { $0 }
    }

    /// Initial great-circle bearing in degrees (0 = north, clockwise).
    static func bearing(from a: CLLocationCoordinate2D, to b: CLLocationCoordinate2D) -> Double {
        let lat1 = a.latitude * .pi / 180, lat2 = b.latitude * .pi / 180
        let dLon = (b.longitude - a.longitude) * .pi / 180
        let y = sin(dLon) * cos(lat2)
        let x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLon)
        let degrees = atan2(y, x) * 180 / .pi
        return (degrees + 360).truncatingRemainder(dividingBy: 360)
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}
