from esida.copernicus_parameter import CopernicusParameter

class copernicus_moss(CopernicusParameter):

    def __init__(self):
        super().__init__()

        self.area_of_interest = [
            'moss_lichen',
        ]
