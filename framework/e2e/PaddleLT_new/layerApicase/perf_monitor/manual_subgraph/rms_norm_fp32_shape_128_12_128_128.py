"""a rms subgraph"""
import unittest  # docstring
import numpy as np  # docstring
import paddle  # docstring


class LayerCase(paddle.nn.Layer):  # docstring
    """
    layer case
    """

    def __init__(self):
        """as you can see this is init"""
        super().__init__()
        self.variance_epsilon = 1e-6

    def forward(self, hidden_states, weight):
        """and this is forward"""
        return paddle.incubate.nn.functional.fused_rms_norm(
            x=hidden_states,
            norm_weight=weight,
            norm_bias=None,
            epsilon=self.variance_epsilon,
            begin_norm_axis=3,
        )


def create_tensor_inputs():
    """
    create tensor inputs
    """
    shape = [128, 12, 128, 128]
    shape = [128, 12, 128, 128]
    x = paddle.uniform(shape, dtype="float32", min=-0.5, max=0.5)
    x.stop_gradient = False
    weight = paddle.ones(shape=[shape[-1]], dtype="float32")
    weight.stop_gradient = False

    inputs = (x, weight)
    return inputs


# def create_numpy_inputs():
#     shape = [1, 13, 4096]
#     x = np.random.uniform(low=-0.5, high=0.5, size=(1, 13, 4096))
#     weight = np.ones((4096), dtype="float32")
#     inputs = (x, weight)
#     return inputs


# class PaddleRMSNormSubGraph(paddle.nn.Layer):
#     def __init__(self):
#         super().__init__()
#         self.variance_epsilon = 1e-6

#     def forward(self, hidden_states, weight):
#         return paddle.incubate.nn.functional.fused_rms_norm(
#             x=hidden_states,
#             norm_weight=weight,
#             norm_bias=None,
#             epsilon=self.variance_epsilon,
#             begin_norm_axis=3,
#         )


# class TestRMSNormSubGraph(unittest.TestCase):
#     def setUp(self):
#         paddle.seed(2022)
#         self.prepare_data()

#     def prepare_data(self):
#         self.x, self.weight = create_tensor_inputs()

#     def apply_to_static(self, net, use_cinn, input_spec=None):
#         build_strategy = paddle.static.BuildStrategy()
#         build_strategy.build_cinn_pass = use_cinn
#         return paddle.jit.to_static(
#             net,
#             input_spec=input_spec,
#             build_strategy=build_strategy,
#             full_graph=True,
#         )

#     def train(self, use_cinn):
#         if use_cinn:
#             net = LayerCase()
#         else:
#             net = PaddleRMSNormSubGraph()
#         net.eval()
#         net = self.apply_to_static(net, use_cinn)
#         for i in range(10000):
#             out = net(self.x, self.weight)
#         return out

#     def test_train(self):
#         cinn_out = self.train(use_cinn=True)

#         dy_out = self.train(use_cinn=False)
#         np.testing.assert_allclose(cinn_out.numpy(), dy_out.numpy(), atol=1e-6, rtol=1e-6)


# if __name__ == "__main__":
#     unittest.main()
