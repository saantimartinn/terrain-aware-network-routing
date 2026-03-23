# Grid-Based Access Routing

FOR each POI:
    find nearest road segment

    build local grid between POI and road

    compute intersections with road network

    construct temporary graph

    route from POI to road

    IF no valid path:
        connect directly (fallback)