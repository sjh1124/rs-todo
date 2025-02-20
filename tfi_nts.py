import torch
import torch.nn as nn
import torch.optim as optim
from .layers import EmbeddingLayer, MultiLayerPerceptron



# 模型定义
class TFI_NTS(nn.Module):
    def __init__(self, categorical_field_dims, numerical_num, embed_dim, bottom_mlp_dims, tower_mlp_dims, task_num,
                 expert_num, dropout):
        super().__init__()
        # self.alpha = [torch.tensor(0.5, requires_grad=False, dtype=torch.float32), torch.tensor(0.5, requires_grad=False, dtype=torch.float32)]
        self.embedding = EmbeddingLayer(categorical_field_dims, embed_dim)
        self.numerical_layer = torch.nn.Linear(numerical_num, embed_dim)
        self.embed_output_dim = (len(categorical_field_dims) + 1) * embed_dim
        self.task_num = task_num
        self.expert_num = expert_num

        self.expert = torch.nn.ModuleList(
            [MultiLayerPerceptron(self.embed_output_dim, bottom_mlp_dims, dropout, output_layer=False) for i in
             range(expert_num)])
        self.tower = torch.nn.ModuleList(
            [MultiLayerPerceptron(bottom_mlp_dims[-1], tower_mlp_dims, dropout) for i in range(task_num)])
        self.gate = torch.nn.ModuleList(
            [torch.nn.Sequential(torch.nn.Linear(self.embed_output_dim, expert_num), torch.nn.Softmax(dim=1)) for i in
             range(task_num)])

        self.task_exclusive = torch.nn.ModuleList(
            [MultiLayerPerceptron(self.embed_output_dim, bottom_mlp_dims, dropout, output_layer=False) for i in
             range(task_num)])



    def forward(self, alpha, categorical_x, numerical_x):
        categorical_emb = self.embedding(categorical_x)
        numerical_emb = self.numerical_layer(numerical_x).unsqueeze(1)
        emb = torch.cat([categorical_emb, numerical_emb], 1).view(-1, self.embed_output_dim)

        gate_value = [self.gate[i](emb).unsqueeze(1) for i in range(self.task_num)]
        share_fea = torch.cat([self.expert[i](emb).unsqueeze(1) for i in range(self.expert_num)], dim=1)

        task_share_fea = [torch.bmm(gate_value[i], share_fea).squeeze(1) for i in range(self.task_num)]
        task_special_fea = [self.task_exclusive[i](emb) for i in range(self.task_num)]
        task_fea = [alpha[i] * task_special_fea[i] + (1 - alpha[i]) * task_share_fea[i] for i in range(self.task_num)]

        results = [torch.sigmoid(self.tower[i](task_fea[i]).squeeze(1)) for i in range(self.task_num)]




        return results


