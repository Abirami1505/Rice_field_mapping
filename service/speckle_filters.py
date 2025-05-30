import ee

def boxcar(image: ee.Image,radius=2):
    original_band_name=image.bandNames()

    filtered_img=image.reduceNeighborhood(
        reducer=ee.Reducer.median(),
        kernel=ee.Kernel.square(radius)
    )

    filtered_img=filtered_img.rename(original_band_name)
    filtered_img=filtered_img.copyProperties(image,["system:time_start"])

    return filtered_img